#pragma once

#include "esphome/core/component.h"
#include "esphome/core/automation.h"
#include "esphome/core/log.h"

#ifdef USE_ESP32
#include "esphome/components/lvgl/lottie_loader.h"
#endif

#include <string>
#include <vector>
#include <map>

namespace esphome {
namespace lottie_state_machine {

static const char *const TAG = "lottie_sm";

struct StateDefinition {
  std::string name;
  int32_t start_frame;
  int32_t end_frame;
  bool loop;
};

class LottieStateMachineComponent : public Component {
 public:
  void set_lottie_id(const std::string &id) { this->lottie_id_ = id; }
  void set_name(const std::string &name) { this->name_ = name; }

  void add_state(const std::string &name, int32_t start, int32_t end, bool loop) {
    StateDefinition s;
    s.name = name;
    s.start_frame = start;
    s.end_frame = end;
    s.loop = loop;
    this->states_[name] = s;
  }

  void add_state_name(const std::string &name) {
    this->state_names_.push_back(name);
  }

  void set_initial_state(const std::string &state) { this->initial_state_ = state; }

  float get_setup_priority() const override { return setup_priority::LATE; }

  void setup() override {
    ESP_LOGI(TAG, "Lottie State Machine '%s' initialized with %d states",
             this->name_.c_str(), (int)this->states_.size());
    for (auto &pair : this->states_) {
      ESP_LOGI(TAG, "  State '%s': frames %d-%d, loop=%d",
               pair.first.c_str(), (int)pair.second.start_frame,
               (int)pair.second.end_frame, (int)pair.second.loop);
    }
  }

  // --- Public API ---

  void set_playing(bool playing) {
#if LV_USE_LOTTIE
    if (this->ctx_ == nullptr) return;
    if (playing) {
      lvgl::lottie_play(this->ctx_);
    } else {
      lvgl::lottie_pause(this->ctx_);
    }
    this->is_playing_ = playing;
    ESP_LOGI(TAG, "%s → %s", this->name_.c_str(), playing ? "PLAYING" : "PAUSED");
#endif
  }

  void set_state(const std::string &state_name) {
#if LV_USE_LOTTIE
    if (this->ctx_ == nullptr) {
      ESP_LOGW(TAG, "Context not set, cannot change state");
      return;
    }

    auto it = this->states_.find(state_name);
    if (it == this->states_.end()) {
      ESP_LOGW(TAG, "Unknown state: %s", state_name.c_str());
      return;
    }

    auto &s = it->second;
    this->current_state_ = state_name;

    this->ctx_->start_frame = s.start_frame;
    this->ctx_->end_frame = s.end_frame;
    this->ctx_->loop = s.loop;

    lvgl::lottie_restart(this->ctx_);
    this->is_playing_ = true;

    ESP_LOGI(TAG, "%s → State '%s' (frames %d-%d, loop=%d)",
             this->name_.c_str(), state_name.c_str(),
             (int)s.start_frame, (int)s.end_frame, (int)s.loop);
#endif
  }

  void go_to_frame(int32_t frame) {
#if LV_USE_LOTTIE
    if (this->ctx_ == nullptr || this->ctx_->exec_cb == nullptr) return;
    lv_lock();
    this->ctx_->exec_cb(this->ctx_->anim_var, frame);
    lv_unlock();
    lvgl::lottie_pause(this->ctx_);
    this->is_playing_ = false;
    ESP_LOGI(TAG, "%s → Frame %d", this->name_.c_str(), (int)frame);
#endif
  }

  const std::string &get_current_state() const { return this->current_state_; }
  bool is_playing() const { return this->is_playing_; }
  const std::vector<std::string> &get_state_names() const { return this->state_names_; }

#if LV_USE_LOTTIE
  void set_context(lvgl::LottieContext *ctx) {
    this->ctx_ = ctx;
    if (!this->initial_state_.empty()) {
      this->set_state(this->initial_state_);
    }
  }
  lvgl::LottieContext *get_context() { return this->ctx_; }
#endif

 protected:
  std::string lottie_id_;
  std::string name_;
  std::string initial_state_;
  std::string current_state_;
  bool is_playing_{false};

  std::map<std::string, StateDefinition> states_;
  std::vector<std::string> state_names_;

#if LV_USE_LOTTIE
  lvgl::LottieContext *ctx_{nullptr};
#endif
};

// --- Action: set_state ---
template<typename... Ts> class LottieSetStateAction : public Action<Ts...> {
 public:
  LottieSetStateAction(LottieStateMachineComponent *parent) : parent_(parent) {}

  TEMPLATABLE_VALUE(std::string, state)

  void play(const Ts &...x) override {
    this->parent_->set_state(this->state_.value(x...));
  }

 protected:
  LottieStateMachineComponent *parent_;
};

}  // namespace lottie_state_machine
}  // namespace esphome
