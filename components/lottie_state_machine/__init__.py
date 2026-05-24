"""
Lottie State Machine for ESPHome LVGL.

Generic state machine that auto-detects Lottie animation info and exposes
controls in Home Assistant:

  - switch: Play / Pause
  - select: State selection (from markers or YAML-defined states)
  - number: Playback speed (0.1x to 3.0x)
  - number: Go to frame
  - sensor: Current state name + current frame

Usage:

    lottie_state_machine:
      id: lottie_sm
      lottie_id: my_lottie
      name: "Robot Animation"

      # Optional: define custom states with frame segments
      # If not defined, the full animation plays as a single state
      states:
        idle:
          segment: [0, 60]
          loop: true
        active:
          segment: [61, 120]
          loop: false
        alert:
          segment: [121, 180]
          loop: true

All entities are auto-created in Home Assistant.
State can be changed from HA or from YAML automations:

    - lottie_state_machine.set_state:
        id: lottie_sm
        state: alert
"""

import json
from pathlib import Path

import esphome.automation as automation
import esphome.codegen as cg
import esphome.config_validation as cv
from esphome.components import number, select, sensor, switch
from esphome.const import (
    CONF_ID,
    CONF_NAME,
    CONF_STATE,
    ENTITY_CATEGORY_CONFIG,
    ENTITY_CATEGORY_DIAGNOSTIC,
    ICON_RESTART,
    UNIT_EMPTY,
)
from esphome.core import CORE

CODEOWNERS = ["@youkorr"]
DEPENDENCIES = ["lvgl"]
AUTO_LOAD = ["switch", "select", "number", "sensor"]

CONF_LOTTIE_ID = "lottie_id"
CONF_STATES = "states"
CONF_SEGMENT = "segment"
CONF_LOOP = "loop"
CONF_INITIAL_STATE = "initial_state"
CONF_LOTTIE_SM_ID = "lottie_state_machine_id"

lottie_sm_ns = cg.esphome_ns.namespace("lottie_state_machine")
LottieStateMachineComponent = lottie_sm_ns.class_(
    "LottieStateMachineComponent", cg.Component
)
LottiePlaySwitch = lottie_sm_ns.class_("LottiePlaySwitch", switch.Switch)
LottieStateSelect = lottie_sm_ns.class_("LottieStateSelect", select.Select)
LottieSpeedNumber = lottie_sm_ns.class_("LottieSpeedNumber", number.Number)
LottieFrameNumber = lottie_sm_ns.class_("LottieFrameNumber", number.Number)
LottieStateSensor = lottie_sm_ns.class_("LottieStateSensor", sensor.Sensor)
LottieFrameSensor = lottie_sm_ns.class_("LottieFrameSensor", sensor.Sensor)

# Action
LottieSetStateAction = lottie_sm_ns.class_("LottieSetStateAction", automation.Action)

STATE_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_SEGMENT): cv.All(
            cv.ensure_list(cv.int_), cv.Length(min=2, max=2)
        ),
        cv.Optional(CONF_LOOP, default=True): cv.boolean,
    }
)

CONFIG_SCHEMA = cv.Schema(
    {
        cv.GenerateID(): cv.declare_id(LottieStateMachineComponent),
        cv.Required(CONF_LOTTIE_ID): cv.string,
        cv.Optional(CONF_NAME, default="Lottie"): cv.string,
        cv.Optional(CONF_STATES, default={}): cv.Schema(
            {cv.string: STATE_SCHEMA}
        ),
        cv.Optional(CONF_INITIAL_STATE): cv.string,
    }
).extend(cv.COMPONENT_SCHEMA)

SET_STATE_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_ID): cv.use_id(LottieStateMachineComponent),
        cv.Required(CONF_STATE): cv.templatable(cv.string),
    }
)


async def to_code(config):
    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)

    cg.add(var.set_lottie_id(config[CONF_LOTTIE_ID]))

    name = config[CONF_NAME]

    # Register states
    states = config.get(CONF_STATES, {})
    state_names = []
    for state_name, state_config in states.items():
        seg = state_config[CONF_SEGMENT]
        loop = state_config[CONF_LOOP]
        cg.add(var.add_state(state_name, seg[0], seg[1], loop))
        state_names.append(state_name)

    if initial := config.get(CONF_INITIAL_STATE):
        cg.add(var.set_initial_state(initial))
    elif state_names:
        cg.add(var.set_initial_state(state_names[0]))

    # Play/Pause Switch
    play_switch = cg.new_Pvariable(cv.declare_id(LottiePlaySwitch)())
    await switch.register_switch(
        play_switch,
        {
            "name": f"{name} Play",
            "icon": "mdi:play-pause",
        },
    )
    cg.add(var.set_play_switch(play_switch))
    cg.add(play_switch.set_parent(var))

    # State Select (only if states defined)
    if state_names:
        state_select = cg.new_Pvariable(cv.declare_id(LottieStateSelect)())
        await select.register_select(
            state_select,
            {
                "name": f"{name} State",
                "icon": "mdi:state-machine",
                "options": state_names,
            },
        )
        cg.add(var.set_state_select(state_select))
        cg.add(state_select.set_parent(var))

    # Speed Number
    speed_num = cg.new_Pvariable(cv.declare_id(LottieSpeedNumber)())
    await number.register_number(
        speed_num,
        {
            "name": f"{name} Speed",
            "icon": "mdi:speedometer",
            "min_value": 0.1,
            "max_value": 3.0,
            "step": 0.1,
            "entity_category": ENTITY_CATEGORY_CONFIG,
        },
    )
    cg.add(var.set_speed_number(speed_num))
    cg.add(speed_num.set_parent(var))

    # Frame Number
    frame_num = cg.new_Pvariable(cv.declare_id(LottieFrameNumber)())
    await number.register_number(
        frame_num,
        {
            "name": f"{name} Frame",
            "icon": "mdi:filmstrip",
            "min_value": 0,
            "max_value": 10000,
            "step": 1,
            "entity_category": ENTITY_CATEGORY_CONFIG,
        },
    )
    cg.add(var.set_frame_number(frame_num))
    cg.add(frame_num.set_parent(var))

    # Current State Sensor
    state_sensor = cg.new_Pvariable(cv.declare_id(LottieStateSensor)())
    await sensor.register_sensor(
        state_sensor,
        {
            "name": f"{name} Current Frame",
            "icon": "mdi:animation-play",
            "accuracy_decimals": 0,
            "entity_category": ENTITY_CATEGORY_DIAGNOSTIC,
        },
    )
    cg.add(var.set_frame_sensor(state_sensor))


@automation.register_action(
    "lottie_state_machine.set_state",
    LottieSetStateAction,
    SET_STATE_SCHEMA,
    synchronous=True,
)
async def lottie_set_state_to_code(config, action_id, template_arg, args):
    parent = await cg.get_variable(config[CONF_ID])
    var = cg.new_Pvariable(action_id, template_arg, parent)
    templ = await cg.templatable(config[CONF_STATE], args, cg.std_string)
    cg.add(var.set_state(templ))
    return var
