#pragma once

#ifdef USE_ESP32

#include <lvgl.h>
#if LV_USE_LOTTIE

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include <cstring>

#include <src/widgets/lottie/lv_lottie_private.h>

namespace esphome {
namespace lvgl {

static const char *const LOTTIE_TAG = "lottie";
static constexpr size_t LOTTIE_TASK_STACK_SIZE = 64 * 1024;

// State machine states
enum LottieState : uint8_t {
    LOTTIE_STATE_STOPPED = 0,
    LOTTIE_STATE_PLAYING,
    LOTTIE_STATE_PAUSED,
};

struct LottieContext {
    // --- Config (set once, never freed) ---
    lv_obj_t *obj;
    const void *data;
    size_t data_size;
    const char *file_path;
    bool loop;
    bool auto_start;
    uint32_t width;
    uint32_t height;

    // --- Animation params (captured on first load, reused on re-loads) ---
    lv_anim_exec_xcb_t exec_cb;
    void *anim_var;
    int32_t start_frame;
    int32_t end_frame;
    uint32_t duration_ms;
    bool data_loaded;

    // --- Runtime state ---
    uint8_t *pixel_buffer;
    StackType_t *task_stack;
    StaticTask_t *task_tcb;
    TaskHandle_t task_handle;
    volatile bool stop_requested;
    volatile LottieState state;
    volatile bool restart_requested;
    TickType_t start_tick;
    TickType_t pause_elapsed_ms;
    bool user_wants_hidden;
    bool runtime_hidden;
};

// --------------------------------------------------------------------------
// Render task – runs on 64 KB PSRAM stack
// --------------------------------------------------------------------------
inline void lottie_load_task(void *param) {
    LottieContext *ctx = (LottieContext *)param;

    vTaskDelay(pdMS_TO_TICKS(ctx->data_loaded ? 100 : 1000));

    lv_lock();

    if (!ctx->data_loaded) {
        ESP_LOGI(LOTTIE_TAG, "First load: parsing lottie data...");

        lv_lottie_set_buffer(ctx->obj, ctx->width, ctx->height, ctx->pixel_buffer);

        if (ctx->data != nullptr) {
            lv_lottie_set_src_data(ctx->obj, ctx->data, ctx->data_size);
            ESP_LOGI(LOTTIE_TAG, "Data loaded from embedded source (%d bytes)", (int)ctx->data_size);
        } else if (ctx->file_path != nullptr) {
            lv_lottie_set_src_file(ctx->obj, ctx->file_path);
            ESP_LOGI(LOTTIE_TAG, "Data loaded from file: %s", ctx->file_path);
        }

        lv_anim_t *anim = lv_lottie_get_anim(ctx->obj);
        if (anim != nullptr) {
            ctx->exec_cb     = anim->exec_cb;
            ctx->anim_var    = anim->var;
            ctx->start_frame = anim->start_value;
            ctx->end_frame   = anim->end_value;
            ctx->duration_ms = (uint32_t)lv_anim_get_time(anim);

            ESP_LOGI(LOTTIE_TAG, "Anim: frames %d..%d, duration %u ms",
                     (int)ctx->start_frame, (int)ctx->end_frame, (unsigned)ctx->duration_ms);

            lv_anim_delete(ctx->anim_var, ctx->exec_cb);

            lv_lottie_t *lottie = (lv_lottie_t *)ctx->obj;
            lottie->anim = NULL;

            ctx->data_loaded = true;
            ESP_LOGI(LOTTIE_TAG, "LVGL anim removed – rendering from PSRAM task");
        } else {
            ESP_LOGE(LOTTIE_TAG, "Animation INVALID – parsing may have failed!");
        }
    } else {
        ESP_LOGI(LOTTIE_TAG, "Re-load: updating buffer (no re-parse)");

        lv_lottie_t *lottie = (lv_lottie_t *)ctx->obj;
        tvg_canvas_clear(lottie->tvg_canvas, false);

        lv_lottie_set_buffer(ctx->obj, ctx->width, ctx->height, ctx->pixel_buffer);
    }

    if (!ctx->runtime_hidden) {
        lv_obj_remove_flag(ctx->obj, LV_OBJ_FLAG_HIDDEN);
    }

    lv_unlock();

    // Validate animation parameters
    if (!ctx->data_loaded || ctx->exec_cb == nullptr ||
        ctx->duration_ms == 0 || ctx->end_frame <= ctx->start_frame) {
        ESP_LOGW(LOTTIE_TAG, "No valid animation, task suspending");
        vTaskSuspend(NULL);
        return;
    }

    // Set initial state based on auto_start
    if (ctx->auto_start) {
        ctx->state = LOTTIE_STATE_PLAYING;
    } else {
        ctx->state = LOTTIE_STATE_STOPPED;
        ESP_LOGI(LOTTIE_TAG, "auto_start=false, state=STOPPED");
    }

    // --- Frame render loop with state machine ---
    int32_t total_frames = ctx->end_frame - ctx->start_frame;
    uint32_t frame_delay_ms = ctx->duration_ms / (uint32_t)total_frames;
    if (frame_delay_ms < 16)  frame_delay_ms = 16;
    if (frame_delay_ms > 100) frame_delay_ms = 100;

    ESP_LOGI(LOTTIE_TAG, "Render loop: %u ms/frame, loop=%d, state=%s",
             (unsigned)frame_delay_ms, (int)ctx->loop,
             ctx->state == LOTTIE_STATE_PLAYING ? "PLAYING" : "STOPPED");

    ctx->start_tick = xTaskGetTickCount();
    ctx->pause_elapsed_ms = 0;

    while (!ctx->stop_requested) {

        // Handle state transitions
        switch (ctx->state) {

            case LOTTIE_STATE_PLAYING: {
                if (ctx->restart_requested) {
                    ctx->start_tick = xTaskGetTickCount();
                    ctx->pause_elapsed_ms = 0;
                    ctx->restart_requested = false;
                    ESP_LOGI(LOTTIE_TAG, "Animation restarted from frame 0");
                }

                uint32_t elapsed_ms = ctx->pause_elapsed_ms +
                    (uint32_t)((xTaskGetTickCount() - ctx->start_tick) * portTICK_PERIOD_MS);

                int32_t frame;
                if (ctx->loop) {
                    uint32_t phase = elapsed_ms % ctx->duration_ms;
                    frame = ctx->start_frame + (int32_t)((int64_t)total_frames * phase / ctx->duration_ms);
                } else {
                    if (elapsed_ms >= ctx->duration_ms) {
                        lv_lock();
                        ctx->exec_cb(ctx->anim_var, ctx->end_frame);
                        lv_unlock();
                        ctx->state = LOTTIE_STATE_STOPPED;
                        ESP_LOGI(LOTTIE_TAG, "Animation complete → STOPPED");
                        continue;
                    }
                    frame = ctx->start_frame + (int32_t)((int64_t)total_frames * elapsed_ms / ctx->duration_ms);
                }

                lv_lock();
                ctx->exec_cb(ctx->anim_var, frame);
                lv_unlock();
                break;
            }

            case LOTTIE_STATE_PAUSED:
                // Do nothing, just wait
                break;

            case LOTTIE_STATE_STOPPED:
                // Do nothing, just wait
                break;
        }

        vTaskDelay(pdMS_TO_TICKS(frame_delay_ms));
    }

    ESP_LOGI(LOTTIE_TAG, "Stop requested – task suspending");
    vTaskSuspend(NULL);
}

// --------------------------------------------------------------------------
// State machine API – safe to call from any context
// --------------------------------------------------------------------------
inline void lottie_play(LottieContext *ctx) {
    if (!ctx || !ctx->task_handle) return;
    if (ctx->state == LOTTIE_STATE_PAUSED) {
        // Resume: adjust start_tick to account for elapsed time before pause
        ctx->start_tick = xTaskGetTickCount();
    } else if (ctx->state == LOTTIE_STATE_STOPPED) {
        // Start from beginning
        ctx->start_tick = xTaskGetTickCount();
        ctx->pause_elapsed_ms = 0;
    }
    ctx->state = LOTTIE_STATE_PLAYING;
    ESP_LOGI(LOTTIE_TAG, "State → PLAYING");
}

inline void lottie_pause(LottieContext *ctx) {
    if (!ctx || !ctx->task_handle) return;
    if (ctx->state == LOTTIE_STATE_PLAYING) {
        // Save elapsed time so we can resume from here
        ctx->pause_elapsed_ms +=
            (uint32_t)((xTaskGetTickCount() - ctx->start_tick) * portTICK_PERIOD_MS);
        ctx->state = LOTTIE_STATE_PAUSED;
        ESP_LOGI(LOTTIE_TAG, "State → PAUSED (elapsed %u ms)", (unsigned)ctx->pause_elapsed_ms);
    }
}

inline void lottie_stop(LottieContext *ctx) {
    if (!ctx || !ctx->task_handle) return;
    ctx->pause_elapsed_ms = 0;
    ctx->state = LOTTIE_STATE_STOPPED;
    // Reset to first frame
    if (ctx->exec_cb) {
        lv_lock();
        ctx->exec_cb(ctx->anim_var, ctx->start_frame);
        lv_unlock();
    }
    ESP_LOGI(LOTTIE_TAG, "State → STOPPED (reset to frame 0)");
}

inline void lottie_restart(LottieContext *ctx) {
    if (!ctx || !ctx->task_handle) return;
    ctx->restart_requested = true;
    ctx->state = LOTTIE_STATE_PLAYING;
    ESP_LOGI(LOTTIE_TAG, "Restart requested → PLAYING");
}

// --------------------------------------------------------------------------
// Free all PSRAM/internal-RAM resources
// --------------------------------------------------------------------------
inline void lottie_free_resources(LottieContext *ctx) {
    ctx->stop_requested = true;
    if (ctx->task_handle) {
        vTaskDelete(ctx->task_handle);
        ctx->task_handle = nullptr;
    }
    if (ctx->task_stack)    { heap_caps_free(ctx->task_stack);    ctx->task_stack = nullptr; }
    if (ctx->task_tcb)      { heap_caps_free(ctx->task_tcb);      ctx->task_tcb = nullptr; }
    if (ctx->pixel_buffer)  { heap_caps_free(ctx->pixel_buffer);  ctx->pixel_buffer = nullptr; }
    ctx->stop_requested = false;
    ctx->state = LOTTIE_STATE_STOPPED;

    ESP_LOGI(LOTTIE_TAG, "Lottie PSRAM freed (%ux%u = %u KB + 64 KB stack)",
             (unsigned)ctx->width, (unsigned)ctx->height,
             (unsigned)(ctx->width * ctx->height * 4 / 1024));
}

// --------------------------------------------------------------------------
// (Re-)allocate pixel buffer and launch the render task
// --------------------------------------------------------------------------
inline bool lottie_launch(LottieContext *ctx) {
    size_t buf_bytes = (size_t)ctx->width * ctx->height * 4;
    ctx->pixel_buffer = (uint8_t *)heap_caps_malloc(
        buf_bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    if (!ctx->pixel_buffer) {
        ESP_LOGE(LOTTIE_TAG, "PSRAM alloc failed (%u bytes)", (unsigned)buf_bytes);
        return false;
    }
    memset(ctx->pixel_buffer, 0, buf_bytes);

    lv_obj_add_flag(ctx->obj, LV_OBJ_FLAG_HIDDEN);

    ctx->task_stack = (StackType_t *)heap_caps_malloc(
        LOTTIE_TASK_STACK_SIZE, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
    ctx->task_tcb = (StaticTask_t *)heap_caps_malloc(
        sizeof(StaticTask_t), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!ctx->task_stack || !ctx->task_tcb) {
        ESP_LOGE(LOTTIE_TAG, "Task alloc failed");
        lottie_free_resources(ctx);
        return false;
    }

    ctx->stop_requested = false;
    ctx->state = LOTTIE_STATE_STOPPED;
    ctx->task_handle = xTaskCreateStatic(
        lottie_load_task, "lottie_anim",
        LOTTIE_TASK_STACK_SIZE / sizeof(StackType_t),
        ctx, 5, ctx->task_stack, ctx->task_tcb);

    if (!ctx->task_handle) {
        lottie_free_resources(ctx);
        return false;
    }

    ESP_LOGI(LOTTIE_TAG, "Lottie launched (runtime_hidden=%d, PSRAM: %u KB buf + 64 KB stack, free PSRAM: %u KB, free SRAM: %u KB)",
             (int)ctx->runtime_hidden,
             (unsigned)(buf_bytes / 1024),
             (unsigned)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024),
             (unsigned)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024));
    return true;
}

// --------------------------------------------------------------------------
// Screen event callbacks
// --------------------------------------------------------------------------
inline void lottie_screen_unload_start_cb(lv_event_t *e) {
    LottieContext *ctx = (LottieContext *)lv_event_get_user_data(e);

    ctx->runtime_hidden = lv_obj_has_flag(ctx->obj, LV_OBJ_FLAG_HIDDEN);
    ctx->stop_requested = true;
    lv_obj_add_flag(ctx->obj, LV_OBJ_FLAG_HIDDEN);

    ESP_LOGI(LOTTIE_TAG, "Lottie task stopped, widget hidden (was_hidden=%d)", (int)ctx->runtime_hidden);
}

inline void lottie_screen_unloaded_cb(lv_event_t *e) {
    LottieContext *ctx = (LottieContext *)lv_event_get_user_data(e);

    if (ctx->task_handle) {
        for (int i = 0; i < 50; i++) {
            if (eTaskGetState(ctx->task_handle) == eSuspended) break;
            vTaskDelay(pdMS_TO_TICKS(5));
        }
        vTaskDelete(ctx->task_handle);
        ctx->task_handle = nullptr;
    }
    if (ctx->task_stack)    { heap_caps_free(ctx->task_stack);    ctx->task_stack = nullptr; }
    if (ctx->task_tcb)      { heap_caps_free(ctx->task_tcb);      ctx->task_tcb = nullptr; }
    if (ctx->pixel_buffer)  { heap_caps_free(ctx->pixel_buffer);  ctx->pixel_buffer = nullptr; }
    ctx->stop_requested = false;
    ctx->state = LOTTIE_STATE_STOPPED;

    ESP_LOGI(LOTTIE_TAG, "Lottie FREED (%ux%u = %u KB buf + 64 KB stack) → free PSRAM: %u KB, free SRAM: %u KB",
             (unsigned)ctx->width, (unsigned)ctx->height,
             (unsigned)(ctx->width * ctx->height * 4 / 1024),
             (unsigned)(heap_caps_get_free_size(MALLOC_CAP_SPIRAM) / 1024),
             (unsigned)(heap_caps_get_free_size(MALLOC_CAP_INTERNAL) / 1024));
}

inline void lottie_screen_loaded_cb(lv_event_t *e) {
    LottieContext *ctx = (LottieContext *)lv_event_get_user_data(e);
    if (ctx->pixel_buffer == nullptr) {
        lottie_launch(ctx);
    }
}

// --------------------------------------------------------------------------
// Public API: initialise Lottie widget
// --------------------------------------------------------------------------
inline bool lottie_init(lv_obj_t *obj, const void *data, size_t data_size,
                         const char *file_path, uint32_t width, uint32_t height,
                         bool loop, bool auto_start, bool user_wants_hidden) {
    LottieContext *ctx = (LottieContext *)heap_caps_malloc(
        sizeof(LottieContext), MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT);
    if (!ctx) return false;
    memset(ctx, 0, sizeof(LottieContext));

    ctx->obj       = obj;
    ctx->data      = data;
    ctx->data_size = data_size;
    ctx->file_path = file_path;
    ctx->loop      = loop;
    ctx->auto_start = auto_start;
    ctx->width     = width;
    ctx->height    = height;
    ctx->user_wants_hidden = user_wants_hidden;
    ctx->runtime_hidden = user_wants_hidden;
    ctx->state     = LOTTIE_STATE_STOPPED;

    lv_obj_set_user_data(obj, ctx);

    lv_obj_t *screen = lv_obj_get_screen(obj);
    lv_obj_add_event_cb(screen, lottie_screen_unload_start_cb,
                        LV_EVENT_SCREEN_UNLOAD_START, ctx);
    lv_obj_add_event_cb(screen, lottie_screen_unloaded_cb,
                        LV_EVENT_SCREEN_UNLOADED, ctx);
    lv_obj_add_event_cb(screen, lottie_screen_loaded_cb,
                        LV_EVENT_SCREEN_LOADED, ctx);

    ESP_LOGI(LOTTIE_TAG, "Lottie registered (%ux%u), waiting for page load to allocate",
             (unsigned)width, (unsigned)height);
    return true;
}

}  // namespace lvgl
}  // namespace esphome

#endif  // LV_USE_LOTTIE
#endif  // USE_ESP32
