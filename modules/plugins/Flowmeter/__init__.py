# -*- coding: utf-8 -*-
# Flowmeter plugin for Craftbeerpi
# Version 1.5 made by nanab
# https://github.com/nanab/Flowmeter
# Some code taken from https://github.com/adafruit/Kegomatic


import time
from modules import cbpi
from modules.core.hardware import ActorBase, SensorPassive
from modules.core.step import StepBase
import json
from flask import Blueprint, render_template, jsonify, request
from modules.core.props import Property, StepProperty

blueprint = Blueprint('flowmeter', __name__)
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
except Exception as e:
    print e
    pass


class FlowMeterData():
    SECONDS_IN_A_MINUTE = 60
    SECONDS_IN_A_HOUR = 3600
    MS_IN_A_SECOND = 1000.0
    enabled = True
    clicks = 0
    lastClick = 0
    clickDelta = 0
    hertz = 0.0
    flow = 0  # in Liters per second
    pour = 0.0  # in Liters

    def __init__(self):
        self.clicks = 0
        self.lastClick = int(time.time() * FlowMeterData.MS_IN_A_SECOND)
        self.clickDelta = 0
        self.lastTenClick = 0
        self.hertz = 0.0
        self.flow = 0.0
        self.pour = 0.0
        self.enabled = True
        self.lstTenDelta = []
        self.totalVolume = 0.00

    def update(self, currentTime, clickPerLiter):
        self.clicks += 1
        self.totalVolume = self.clicks / clickPerLiter # total liters

        # get the time delta
        self.clickDelta = max((currentTime - self.lastClick), 1)
        # calculate the rate of flow
        if self.enabled is True and self.clickDelta < 1000:
            self.lstTenDelta.append(self.clickDelta)

            # Take liters per click and divide by the average ms delta from 10 clicks ,
            if len(self.lstTenDelta) >= 10:
                self.avgTenDelta = sum(self.lstTenDelta) / len(self.lstTenDelta)
                self.pour = ((1/clickPerLiter) / self.avgTenDelta) * 1000
                del self.lstTenDelta[:]
        else:
            self.pour = 0.0

        self.lastClick = currentTime

    def clear(self):
        self.pour = 0.0
        self.clicks = 0
        self.totalVolume = 0.0
        return str(self.pour)


@cbpi.sensor
class Flowmeter(SensorPassive):
    fms = dict()
    gpio = Property.Select("GPIO", options=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27])
    sensorShow = Property.Select("Flowmeter display", options=["Total volume", "Flow, unit/s", "Flow, unit/min", "Flow, unit/h", "Pulse"])
    clickPerLiter = Property.Text("Pulses per Liter (Default value is 450) Requires restart!", configurable=True, default_value="450", description="Here you can adjust the number of clicks/pulses per liter for the flowmeter. With this value you can calibrate the sensor.")
    def init(self):
        unit = cbpi.get_config_parameter("flowunit", None)
        if unit is None:
            print "INIT FLOW DB"
            try:
                cbpi.add_config_parameter("flowunit", "L", "select", "Flowmeter unit", options=["L", "gal(us)", "gal(uk)", "qt"])
            except:
                cbpi.notify("Flowmeter Error", "Unable to update database.", type="danger", timeout=None)
        try:
            GPIO.setup(int(self.gpio),GPIO.IN, pull_up_down = GPIO.PUD_UP)
            GPIO.add_event_detect(int(self.gpio), GPIO.RISING, callback=self.doAClick, bouncetime=2)
            self.fms[int(self.gpio)] = FlowMeterData()
        except Exception as e:
            print e

    def get_unit(self):
        unit = cbpi.get_config_parameter("flowunit", None)
        if self.sensorShow == "Flow, unit/s":
            unit = " " + unit + "/s"
        if self.sensorShow == "Flow, unit/min":
            unit = " " + unit + "/min"
        if self.sensorShow == "Flow, unit/h":
            unit = " " + unit + "/h"
        if self.sensorShow == "Pulse":
            unit = " Pulses"
        return unit

    def doAClick(self, channel):
        currentTime = int(time.time() * FlowMeterData.MS_IN_A_SECOND)
        clickPerLiter = self.clickPerLiter
        self.fms[int(self.gpio)].update(currentTime, float(clickPerLiter))


    def convert(self, inputFlow):
        unit = cbpi.get_config_parameter("flowunit", None)
        if unit == "gal(us)":
            inputFlow = inputFlow * 0.264172052
        elif unit == "gal(uk)":
            inputFlow = inputFlow * 0.219969157
        elif unit == "qt":
            inputFlow = inputFlow * 1.056688
        else:
            pass
        if self.sensorShow == "Flow, unit/s":
            inputFlow = "{0:.2f}".format(inputFlow)
        if self.sensorShow == "Flow, unit/min":
            inputFlow = "{0:.2f}".format(inputFlow*FlowMeterData.SECONDS_IN_A_MINUTE)
        if self.sensorShow == "Flow, unit/h":
            inputFlow = "{0:.2f}".format(inputFlow*FlowMeterData.SECONDS_IN_A_HOUR)
        elif self.sensorShow == "Total volume":
            inputFlow = "{0:.2f}".format(inputFlow)
        #elif self.sensorShow == "Pulse":
            #inputFlow = "{0:.0f}".format(inputFlow)
        else:
            pass
        return inputFlow

    def read(self):
        if self.sensorShow == "Total volume":
            flow = self.fms[int(self.gpio)].totalVolume
            flowConverted = self.convert(flow)
            self.data_received(flowConverted)
        elif self.sensorShow == "Flow, unit/s" or self.sensorShow == "Flow, unit/min":
            # reset flow to zero if no flow.
            self.readCurrentTime = int(time.time() * FlowMeterData.MS_IN_A_SECOND)
            self.readCurrentdelta = self.readCurrentTime - self.fms[int(self.gpio)].lastClick
            if self.readCurrentdelta < 1000:
                flow = self.fms[int(self.gpio)].pour
                flowConverted = self.convert(flow)
                self.data_received(flowConverted)
            else:
                flow = 0.0
                flowConverted = self.convert(flow)
                self.data_received(flowConverted)
        elif self.sensorShow == "Pulse":
            flow = self.fms[int(self.gpio)].clicks
            #flowConverted = self.convert(flow)
            self.data_received(flow)
        else:
            print "error"

    def getValue(self):
        flow = self.fms[int(self.gpio)].totalVolume
        flowConverted = self.convert(flow)
        return flowConverted

    def reset(self):
        self.fms[int(self.gpio)].clear()
        return "Ok"

    @cbpi.action("Reset to zero")
    def resetButton(self):
        self.reset()


@blueprint.route('/<id>/reset', methods=['GET'])
def reset_sensor_value(idt):
    for key, value in cbpi.cache.get("sensors").iteritems():
        if key == int(idt):
            if value.type == "Flowmeter":
                flowReset = value.instance.reset()
                return flowReset
            else:
                return "Sensor is not a Flowmeter"
        else:
            return "Sensor not found"


@blueprint.route('/<id>', methods=['GET'])
def get_sensor_value(idt):
    for key, value in cbpi.cache.get("sensors").iteritems():
        if key == int(idt):
            if value.type == "Flowmeter":
                flowValue = value.instance.getValue()
                return flowValue
            else:
                return "Sensor is not a Flowmeter"
        else:
            return "Sensor not found"


@blueprint.route('/list_all_sensors', methods=['GET'])
def list_all_sensors():
    output = []
    for key, value in cbpi.cache.get("sensors").iteritems():
        output.append({"id": key, "name": value.name, "type": value.type})
    return json.dumps(output)


@cbpi.step
class Flowmeter(StepBase):
    sensor = StepProperty.Sensor("Sensor")
    actorA = StepProperty.Actor("Actor")
    volume = Property.Number("Volume", configurable=True)
    resetFlowmeter = Property.Number("Reset flowmeter when done. 1 = Yes 0 = No", configurable=True, default_value="1")

    def init(self):
        if int(self.actorA) is not None:
            self.actor_on(int(self.actorA))

    @cbpi.action("Turn Actor OFF")
    def start(self):
        if self.actorA is not None:
            self.actor_off(int(self.actorA))

    def reset(self):
        if self.actorA is not None:
            self.actor_off(int(self.actorA))

    def finish(self):
        if self.actorA is not None:
            self.actor_off(int(self.actorA))
        if self.resetFlowmeter == "1":
            for key, value in cbpi.cache.get("sensors").iteritems():
                if key == int(self.sensor):
                    value.instance.reset()

    def execute(self):
        for key, value in cbpi.cache.get("sensors").iteritems():
            if key == int(self.sensor):
                sensorValue = value.instance.getValue()
        if float(sensorValue) >= float(self.volume):
            self.next()


@cbpi.initalizer()
def init(cbpi):
    print "INITIALIZE FlOWMETER SENSOR,ACTOR AND STEP MODULE"
    cbpi.app.register_blueprint(blueprint, url_prefix='/api/flowmeter')
    print "READY"
