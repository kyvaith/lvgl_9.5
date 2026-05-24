"""Switch platform for Lottie State Machine."""

import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import switch
from esphome.const import CONF_ID

from . import (
    CONF_LOTTIE_STATE_MACHINE_ID,
    LottieStateMachine,
    lottie_state_machine_ns,
)

LottieStateMachineSwitch = lottie_state_machine_ns.class_(
    "LottieStateMachineSwitch", switch.Switch, cg.Component
)

CONFIG_SCHEMA = (
    switch.switch_schema(LottieStateMachineSwitch, icon="mdi:animation-play")
    .extend(
        {
            cv.Required(CONF_LOTTIE_STATE_MACHINE_ID): cv.use_id(LottieStateMachine),
        }
    )
    .extend(cv.COMPONENT_SCHEMA)
)


async def to_code(config):
    var = await switch.new_switch(config)
    await cg.register_component(var, config)
    parent = await cg.get_variable(config[CONF_LOTTIE_STATE_MACHINE_ID])
    cg.add(var.set_parent(parent))
