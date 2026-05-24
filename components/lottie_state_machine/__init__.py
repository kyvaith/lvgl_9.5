"""
Lottie State Machine component for ESPHome LVGL.

Provides a switch to enable/disable the state machine that drives
Lottie animations. Some Lottie files require the state machine to
be active for their animations to play.

Usage:
    lottie_state_machine:
      id: lottie_sm
      lottie_id: my_lottie_widget

    switch:
      - platform: lottie_state_machine
        id: lottie_sm_switch
        name: "Lottie Animation"
        lottie_state_machine_id: lottie_sm
"""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.const import CONF_ID

CODEOWNERS = ["@youkorr"]
DEPENDENCIES = ["lvgl"]

CONF_LOTTIE_ID = "lottie_id"
CONF_LOTTIE_STATE_MACHINE_ID = "lottie_state_machine_id"

lottie_state_machine_ns = cg.esphome_ns.namespace("lottie_state_machine")
LottieStateMachine = lottie_state_machine_ns.class_("LottieStateMachine", cg.Component)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(LottieStateMachine),
        cv.Required(CONF_LOTTIE_ID): cv.string,
    }
).extend(cv.COMPONENT_SCHEMA)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_lottie_id(config[CONF_LOTTIE_ID]))
