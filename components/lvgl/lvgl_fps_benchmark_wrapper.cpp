/**
 * @file lvgl_fps_benchmark_wrapper.cpp
 * ESPHome only auto-compiles .cpp files at the component directory root.
 * This wrapper pulls in lvgl_fps_benchmark.c so it's linked into the firmware.
 */

#include "esphome/core/defines.h"

#ifdef USE_LVGL_FPS_BENCHMARK

extern "C" {
#include "lvgl_fps_benchmark.c"
}

#endif /* USE_LVGL_FPS_BENCHMARK */
