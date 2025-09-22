# Piper Radio Module
CircuitPython library for the Piper Radio module

The Piper Radio Module is based on an Espressif ESP32-S2 module with firmware that makes it behave as an i2c peripheral.  It uses ESP-NOW to communicate between modules and it is designed to work with Piper Make when connected to a Raspberry Pi Pico.

## Requirements
This library depends on the CircuitPython `adafruit_bus_device.i2c_device` library and is connected via i2c.  It should be powered at 5v and use 3.3v logic levels on SDA and SCL.
