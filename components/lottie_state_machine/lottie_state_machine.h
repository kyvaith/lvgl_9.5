#pragma once

#include "esphome/core/component.h"
#include "esphome/components/lvgl/lottie_loader.h"

namespace esphome {
namespace lottie_state_machine {

class LottieStateMachine : public Component {
 public:
  void set_lottie_id(const std::string &id) { this->lottie_id_ = id; }
  const std::string &get_lottie_id() const { return this->lottie_id_; }

  void setup() override {}
  float get_setup_priority() const override { return setup_priority::LATE; }

#if LV_USE_LOTTIE
  lvgl::LottieContext *get_context() {
    if (this->ctx_ != nullptr) return this->ctx_;
    // Lazy lookup: find the LottieContext from the LVGL object
    // The context is set via lv_obj_set_user_data() in lottie_init()
    return this->ctx_;
  }

  void set_context(lvgl::LottieContext *ctx) { this->ctx_ = ctx; }

  bool is_playing() {
    auto *ctx = this->get_context();
    if (ctx == nullptr) return false;
    return ctx->state == lvgl::LOTTIE_STATE_PLAYING;
  }

  void start() {
    auto *ctx = this->get_context();
    if (ctx != nullptr) {
      lvgl::lottie_play(ctx);
    }
  }

  void stop() {
    auto *ctx = this->get_context();
    if (ctx != nullptr) {
      lvgl::lottie_stop(ctx);
    }
  }

  void pause() {
    auto *ctx = this->get_context();
    if (ctx != nullptr) {
      lvgl::lottie_pause(ctx);
    }
  }

  void restart() {
    auto *ctx = this->get_context();
    if (ctx != nullptr) {
      lvgl::lottie_restart(ctx);
    }
  }
#else
  bool is_playing() { return false; }
  void start() {}
  void stop() {}
  void pause() {}
  void restart() {}
#endif

 protected:
  std::string lottie_id_;
#if LV_USE_LOTTIE
  lvgl::LottieContext *ctx_{nullptr};
#endif
};

}  // namespace lottie_state_machine
}  // namespace esphome
