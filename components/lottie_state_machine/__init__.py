"""
Lottie State Machine for ESPHome LVGL.

Exposes Lottie animation controls in Home Assistant:
  - switch: Play / Pause
  - select: State selection (from YAML-defined states)
  - number: Playback speed
  - number: Go to frame
  - sensor: Current frame

Usage:
    lottie_state_machine:
      id: lottie_sm
      lottie_id: my_lottie
      name: "Robot"
      states:
        idle:
          segment: [0, 160]
          loop: true
        active:
          segment: [161, 320]
          loop: false
"""

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
)

CODEOWNERS = ["@youkorr"]
DEPENDENCIES = ["lvgl"]
AUTO_LOAD = ["switch", "select", "number", "sensor"]

CONF_LOTTIE_ID = "lottie_id"
CONF_STATES = "states"
CONF_SEGMENT = "segment"
CONF_LOOP = "loop"
CONF_INITIAL_STATE = "initial_state"
CONF_PLAY_SWITCH = "play_switch_id"
CONF_STATE_SELECT = "state_select_id"
CONF_SPEED_NUMBER = "speed_number_id"
CONF_FRAME_NUMBER = "frame_number_id"
CONF_FRAME_SENSOR = "frame_sensor_id"

lottie_sm_ns = cg.esphome_ns.namespace("lottie_state_machine")
LottieStateMachineComponent = lottie_sm_ns.class_(
    "LottieStateMachineComponent", cg.Component
)
LottiePlaySwitch = lottie_sm_ns.class_("LottiePlaySwitch", switch.Switch)
LottieStateSelect = lottie_sm_ns.class_("LottieStateSelect", select.Select)
LottieSpeedNumber = lottie_sm_ns.class_("LottieSpeedNumber", number.Number)
LottieFrameNumber = lottie_sm_ns.class_("LottieFrameNumber", number.Number)
LottieFrameSensor = lottie_sm_ns.class_("LottieFrameSensor", sensor.Sensor)

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
        cv.GenerateID(CONF_PLAY_SWITCH): cv.declare_id(LottiePlaySwitch),
        cv.GenerateID(CONF_STATE_SELECT): cv.declare_id(LottieStateSelect),
        cv.GenerateID(CONF_SPEED_NUMBER): cv.declare_id(LottieSpeedNumber),
        cv.GenerateID(CONF_FRAME_NUMBER): cv.declare_id(LottieFrameNumber),
        cv.GenerateID(CONF_FRAME_SENSOR): cv.declare_id(LottieFrameSensor),
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
        do_loop = state_config[CONF_LOOP]
        cg.add(var.add_state(state_name, seg[0], seg[1], do_loop))
        state_names.append(state_name)

    if initial := config.get(CONF_INITIAL_STATE):
        cg.add(var.set_initial_state(initial))
    elif state_names:
        cg.add(var.set_initial_state(state_names[0]))

    # Play/Pause Switch
    play_sw = cg.new_Pvariable(config[CONF_PLAY_SWITCH])
    await switch.register_switch(play_sw, {
        "name": f"{name} Play",
        "icon": "mdi:play-pause",
    })
    cg.add(var.set_play_switch(play_sw))
    cg.add(play_sw.set_parent(var))

    # State Select
    if state_names:
        state_sel = cg.new_Pvariable(config[CONF_STATE_SELECT])
        await select.register_select(state_sel, {
            "name": f"{name} State",
            "icon": "mdi:state-machine",
            "options": state_names,
        })
        cg.add(var.set_state_select(state_sel))
        cg.add(state_sel.set_parent(var))

    # Speed Number
    speed_num = cg.new_Pvariable(config[CONF_SPEED_NUMBER])
    await number.register_number(speed_num, {
        "name": f"{name} Speed",
        "icon": "mdi:speedometer",
        "min_value": 0.1,
        "max_value": 3.0,
        "step": 0.1,
        "entity_category": ENTITY_CATEGORY_CONFIG,
    })
    cg.add(var.set_speed_number(speed_num))
    cg.add(speed_num.set_parent(var))

    # Frame Number
    frame_num = cg.new_Pvariable(config[CONF_FRAME_NUMBER])
    await number.register_number(frame_num, {
        "name": f"{name} Frame",
        "icon": "mdi:filmstrip",
        "min_value": 0,
        "max_value": 10000,
        "step": 1,
        "entity_category": ENTITY_CATEGORY_CONFIG,
    })
    cg.add(var.set_frame_number(frame_num))
    cg.add(frame_num.set_parent(var))

    # Frame Sensor
    frame_sens = cg.new_Pvariable(config[CONF_FRAME_SENSOR])
    await sensor.register_sensor(frame_sens, {
        "name": f"{name} Current Frame",
        "icon": "mdi:animation-play",
        "accuracy_decimals": 0,
        "entity_category": ENTITY_CATEGORY_DIAGNOSTIC,
    })
    cg.add(var.set_frame_sensor(frame_sens))


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
