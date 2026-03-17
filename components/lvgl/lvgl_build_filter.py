"""
PlatformIO build filter for LVGL on ESP32.

Excludes platform-specific drivers, draw backends, and libraries that are
not relevant for ESP32 targets. Also conditionally excludes ThorVG/SVG/Lottie
when not needed. This significantly reduces compilation time and binary size.

Used as a PlatformIO extra_scripts middleware, added by ESPHome's LVGL component.

The script checks build flags for -DLVGL_USE_THORVG=1 to determine whether
ThorVG-related files should be compiled.
"""

Import("env")

# Check if ThorVG is enabled via build flags set by __init__.py
_build_flags = " ".join(env.get("BUILD_FLAGS", []))
_thorvg_enabled = "LVGL_USE_THORVG=1" in _build_flags


def lvgl_src_filter(env, node):
    """Skip compilation of LVGL source files not needed for ESP32."""
    path = str(node.get_path()).replace("\\", "/")

    # Only filter files inside the LVGL library
    if "/lvgl/" not in path:
        return node

    # ===== Draw backends NOT available on ESP32 =====
    EXCLUDED_DRAW = [
        "/draw/nanovg/",           # NanoVG (OpenGL) - desktop only
        "/draw/nema_gfx/",         # NemaGFX - Renesas/Think Silicon GPU
        "/draw/nxp/",              # NXP PXP/G2D - NXP MCUs only
        "/draw/renesas/",          # Renesas Dave2D - Renesas MCUs only
        "/draw/eve/",              # FT800/FT813 EVE GPU
        "/draw/vg_lite/",          # VG-Lite - NXP/Vivante GPU
        "/draw/dma2d/",            # STM32 DMA2D - STM32 only
        "/draw/sdl/",              # SDL - desktop only
        "/draw/opengles/",         # OpenGL ES - desktop only
    ]

    # ===== Display/input drivers NOT for ESP32 =====
    EXCLUDED_DRIVERS = [
        "/drivers/wayland/",       # Linux Wayland
        "/drivers/x11/",           # Linux X11
        "/drivers/windows/",       # Windows
        "/drivers/sdl/",           # SDL desktop
        "/drivers/nuttx/",         # NuttX RTOS
        "/drivers/qnx/",          # QNX RTOS
        "/drivers/uefi/",          # UEFI firmware
        "/drivers/opengles/",      # OpenGL ES desktop
        "/drivers/draw/eve/",      # EVE display driver
        "/drivers/display/drm/",         # Linux DRM
        "/drivers/display/fb/",          # Linux framebuffer
        "/drivers/display/ft81x/",       # FT81x display
        "/drivers/display/lovyan_gfx/",  # LovyanGFX (handled by ESPHome)
        "/drivers/display/nxp_elcdif/",  # NXP eLCDIF
        "/drivers/display/renesas_glcdc/",  # Renesas GLCDC
        "/drivers/display/st_ltdc/",     # STM32 LTDC
        "/drivers/display/tft_espi/",    # TFT_eSPI (handled by ESPHome)
        "/drivers/display/nv3007/",      # NV3007
        "/drivers/libinput/",      # Linux libinput
        "/drivers/evdev/",         # Linux evdev
    ]

    # ===== Libraries NOT needed on ESP32 =====
    EXCLUDED_LIBS = [
        "/libs/gltf/",             # 3D glTF rendering (OpenGL required)
        "/libs/nanovg/",           # NanoVG (OpenGL required)
        "/libs/ffmpeg/",           # FFmpeg video decoding
        "/libs/freetype/",         # FreeType font engine (use tiny_ttf instead)
        "/libs/rlottie/",          # rlottie (use ThorVG Lottie instead)
        "/libs/libpng/",           # libpng (use pngdec/lodepng instead)
        "/libs/libjpeg_turbo/",    # libjpeg-turbo (use tjpgd instead)
        "/libs/libwebp/",          # libwebp (use ThorVG WebP instead)
        "/libs/frogfs/",           # FrogFS filesystem
        "/libs/vg_lite_driver/",   # VG-Lite driver library
        "/libs/FT800-FT813/",      # FT800/FT813 EVE library
        "/libs/fsdrv/lv_fs_win32.",     # Windows filesystem
        "/libs/fsdrv/lv_fs_uefi.",      # UEFI filesystem
        "/libs/fsdrv/lv_fs_stdio.",     # stdio filesystem (desktop)
        "/libs/fsdrv/lv_fs_arduino_sd.",  # Arduino SD (not ESP-IDF)
        "/libs/fsdrv/lv_fs_arduino_esp_littlefs.",  # Arduino LittleFS
        "/libs/fsdrv/lv_fs_frogfs.",    # FrogFS driver
        "/libs/fsdrv/lv_fs_littlefs.",  # LittleFS driver
    ]

    # ===== OS abstraction layers NOT for ESP32 (uses FreeRTOS) =====
    EXCLUDED_OSAL = [
        "/osal/lv_linux.",          # Linux
        "/osal/lv_windows.",        # Windows
        "/osal/lv_sdl2.",           # SDL2
        "/osal/lv_pthread.",        # POSIX threads
        "/osal/lv_cmsis_rtos2.",    # CMSIS RTOS2
        "/osal/lv_mqx.",            # MQX RTOS
        "/osal/lv_rtthread.",       # RT-Thread
    ]

    # ===== stdlib NOT for ESP32 (uses custom malloc) =====
    EXCLUDED_STDLIB = [
        "/stdlib/micropython/",     # MicroPython
        "/stdlib/rtthread/",        # RT-Thread
        "/stdlib/uefi/",            # UEFI
    ]

    # ===== Debug/test files NOT for production =====
    EXCLUDED_DEBUG = [
        "/debugging/monkey/",               # Monkey testing
        "/debugging/test/",                 # Test helpers
        "/debugging/vg_lite_tvg/",          # VG-Lite ThorVG debug
        "/debugging/sysmon/lv_sysmon.",     # System monitor
    ]

    # Combine all exclusions
    all_excluded = (
        EXCLUDED_DRAW
        + EXCLUDED_DRIVERS
        + EXCLUDED_LIBS
        + EXCLUDED_OSAL
        + EXCLUDED_STDLIB
        + EXCLUDED_DEBUG
    )

    # ===== Conditionally exclude ThorVG/SVG/Lottie when not needed =====
    # This is the biggest flash savings (~500KB-1MB)
    if not _thorvg_enabled:
        all_excluded += [
            "/libs/thorvg/",           # ThorVG vector engine (~500KB+)
            "/libs/lottie/",           # Lottie animation parser
            "/libs/svg/",              # SVG parser
            "/draw/lv_draw_vector.",   # Vector drawing operations
            "/draw/sw/lv_draw_sw_vector.",  # SW vector renderer
        ]

    for pattern in all_excluded:
        if pattern in path:
            return None  # Skip this file

    return node


env.AddBuildMiddleware(lvgl_src_filter)
