#pragma once

#include "esphome/components/switch/switch.h"
#include "esphome/core/component.h"
#include "lottie_state_machine.h"

namespace esphome {
namespace lottie_state_machine {

class LottieStateMachineSwitch : public switch_::Switch, public Component {
 public:
  void set_parent(LottieStateMachine *parent) { this->parent_ = parent; }

  void setup() override {
    bool initial = this->parent_->is_playing();
    this->publish_state(initial);
  }

  float get_setup_priority() const override { return setup_priority::LATE - 1; }

 protected:
  void write_state(bool state) override {
    if (state) {
      this->parent_->start();
    } else {
      this->parent_->stop();
    }
    this->publish_state(state);
  }

  LottieStateMachine *parent_{nullptr};
};

}  // namespace lottie_state_machine
}  // namespace esphome
