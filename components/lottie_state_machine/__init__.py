"""
Lottie State Machine for ESPHome LVGL.

Exposes Lottie animation controls in Home Assistant.
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
CONF_PLAY_SWITCH = "play_switch"
CONF_STATE_SELECT = "state_select"
CONF_SPEED_NUMBER = "speed_number"
CONF_FRAME_NUMBER = "frame_number"
CONF_FRAME_SENSOR = "frame_sensor"

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
        cv.Optional(CONF_PLAY_SWITCH): switch.switch_schema(
            LottiePlaySwitch, icon="mdi:play-pause"
        ),
        cv.Optional(CONF_STATE_SELECT): select.select_schema(
            LottieStateSelect, icon="mdi:state-machine"
        ),
        cv.Optional(CONF_SPEED_NUMBER): number.number_schema(
            LottieSpeedNumber, icon="mdi:speedometer"
        ),
        cv.Optional(CONF_FRAME_NUMBER): number.number_schema(
            LottieFrameNumber, icon="mdi:filmstrip"
        ),
        cv.Optional(CONF_FRAME_SENSOR): sensor.sensor_schema(
            LottieFrameSensor, icon="mdi:animation-play", accuracy_decimals=0
        ),
    }
).extend(cv.COMPONENT_SCHEMA)

SET_STATE_SCHEMA = cv.Schema(
    {
        cv.Required(CONF_ID): cv.use_id(LottieStateMachineComponent),
        cv.Required(CONF_STATE): cv.templatable(cv.string),
    }
)


def _inject_defaults(config, name):
    """Inject default names and auto-generate sub-entity configs if missing."""
    if CONF_PLAY_SWITCH not in config:
        config[CONF_PLAY_SWITCH] = {"name": f"{name} Play"}
    elif "name" not in config[CONF_PLAY_SWITCH]:
        config[CONF_PLAY_SWITCH]["name"] = f"{name} Play"

    if CONF_STATE_SELECT not in config:
        config[CONF_STATE_SELECT] = {"name": f"{name} State"}
    elif "name" not in config[CONF_STATE_SELECT]:
        config[CONF_STATE_SELECT]["name"] = f"{name} State"

    if CONF_SPEED_NUMBER not in config:
        config[CONF_SPEED_NUMBER] = {"name": f"{name} Speed"}
    elif "name" not in config[CONF_SPEED_NUMBER]:
        config[CONF_SPEED_NUMBER]["name"] = f"{name} Speed"

    if CONF_FRAME_NUMBER not in config:
        config[CONF_FRAME_NUMBER] = {"name": f"{name} Frame"}
    elif "name" not in config[CONF_FRAME_NUMBER]:
        config[CONF_FRAME_NUMBER]["name"] = f"{name} Frame"

    if CONF_FRAME_SENSOR not in config:
        config[CONF_FRAME_SENSOR] = {"name": f"{name} Current Frame"}
    elif "name" not in config[CONF_FRAME_SENSOR]:
        config[CONF_FRAME_SENSOR]["name"] = f"{name} Current Frame"

    return config


async def to_code(config):
    name = config[CONF_NAME]
    config = _inject_defaults(config, name)

    var = cg.new_Pvariable(config[CONF_ID])
    await cg.register_component(var, config)
    cg.add(var.set_lottie_id(config[CONF_LOTTIE_ID]))

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
    play_conf = config[CONF_PLAY_SWITCH]
    play_sw = await switch.new_switch(play_conf)
    cg.add(var.set_play_switch(play_sw))
    cg.add(play_sw.set_parent(var))

    # State Select
    if state_names:
        sel_conf = config[CONF_STATE_SELECT]
        state_sel = await select.new_select(sel_conf, options=state_names)
        cg.add(var.set_state_select(state_sel))
        cg.add(state_sel.set_parent(var))

    # Speed Number
    speed_conf = config[CONF_SPEED_NUMBER]
    speed_num = await number.new_number(
        speed_conf, min_value=0.1, max_value=3.0, step=0.1
    )
    cg.add(var.set_speed_number(speed_num))
    cg.add(speed_num.set_parent(var))

    # Frame Number
    frame_conf = config[CONF_FRAME_NUMBER]
    frame_num = await number.new_number(
        frame_conf, min_value=0, max_value=10000, step=1
    )
    cg.add(var.set_frame_number(frame_num))
    cg.add(frame_num.set_parent(var))

    # Frame Sensor
    sens_conf = config[CONF_FRAME_SENSOR]
    frame_sens = await sensor.new_sensor(sens_conf)
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
