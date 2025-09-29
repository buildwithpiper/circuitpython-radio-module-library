PIPER_RADIO_I2C_ADDR = 0x54
REG_RADIO_SELF_ADDR = 0
REG_RADIO_MSG_LEN = 33
REG_RADIO_MSG_IN = 34
REG_RADIO_MSG_SEND = 36

RADIO_COLOR_SENSOR = 0
RADIO_TEMP_SENSOR = 1
RADIO_MOTION_SENSOR = 2
RADIO_HEART_SENSOR = 3
RADIO_MOTOR_MODULE = 4

RADIO_MODULES = [  # Module register, data length
  [40, 8],
  [45, 2],
  [47, 12],
  [54, 4],
]

RADIO_GPIO_INPUT = 0
RADIO_GPIO_INPUT_PULLUP = 4
RADIO_GPIO_INPUT_PULLDOWN = 8
RADIO_GPIO_INPUT_ANALOG = 2
RADIO_GPIO_INPUT_TOUCH = 16
RADIO_GPIO_INPUT_RANGE = 32
RADIO_GPIO_OUTPUT_DIGITAL = 1
RADIO_GPIO_OUTPUT_ANALOG = 3
RADIO_GPIO_OUTPUT_SERVO = 33

import time
import math
from adafruit_bus_device.i2c_device import I2CDevice


# ----------- Methods -----------
class piper_radio_module:
  # Initialize the sensor
  def __init__(self, i2c, address=PIPER_RADIO_I2C_ADDR):
    self.radio = I2CDevice(i2c, address)
    self.peer_addresses = {}  # store peer numbers and their MAC addresses
    self.pin_modes = [0, 0, 0, 0, 0, 0, 0] # store GPIO pin modes

    # Cache for sensor data with timestamp
    self.sensor_cache = {}
    self.cache_timeout = 0.250  # 250ms in seconds

  # format a bytearry into a string representing a MAC address
  def format_mac_string(self, mac_bytes):
    mac_list = list(mac_bytes[:6])
    mac_str = ''.join('{:02x}:'.format(x) for x in mac_list[:5])
    mac_str += '{:02x}'.format(mac_list[-1])
    return mac_str.upper()

  # Check if cached data is still valid
  def _is_cache_valid(self, cache_key):
    if cache_key not in self.sensor_cache:
        return False

    current_time = time.monotonic()
    cache_entry = self.sensor_cache[cache_key]
    return (current_time - cache_entry['timestamp']) < self.cache_timeout

  # Update cache with new data
  def _update_cache(self, cache_key, data):
    self.sensor_cache[cache_key] = {
        'data': data,
        'timestamp': time.monotonic()
    }

  # Get cached data
  def _get_cached_data(self, cache_key):
    return self.sensor_cache[cache_key]['data']

  # request sensor data with caching
  def read_sensor(self, peer, module_type=RADIO_TEMP_SENSOR, value_index=0):
    # Create a unique cache key for this specific sensor reading
    cache_key = f"{peer}_{module_type}_{value_index}"

    # Return cached data if it's still valid
    if self._is_cache_valid(cache_key):
        return self._get_cached_data(cache_key)

    # Otherwise, read from the actual sensor
    if peer > 10 or peer < 0:
      raise ValueError("Peer number must be between 0 and 10")

    bytes_read = bytearray(RADIO_MODULES[module_type][1])
    with self.radio:
      self.radio.write(bytes([RADIO_MODULES[module_type][0], peer]))
      if (peer == 0):
        time.sleep(0.05) # local reads are faster
      else:
        time.sleep(0.2)
      if (peer > 0):
        self.radio.write(bytes([RADIO_MODULES[module_type][0] + 60, 0])) # get the value from the local sensor
      else:
        self.radio.write(bytes([RADIO_MODULES[module_type][0], 0])) # get the value from the remote sensor
      self.radio.readinto(bytes_read)

    result = None

    if (module_type == RADIO_TEMP_SENSOR):
      t = int.from_bytes(bytes_read, "big")
      temp = (t & 0x0FFF) / 16.0
      if (t & 0x1000):
        temp -= 256
      result = temp

    elif (module_type == RADIO_COLOR_SENSOR):
      _c = int.from_bytes(bytes_read[:2], "big")
      _r = int.from_bytes(bytes_read[2:4], "big")
      _g = int.from_bytes(bytes_read[4:6], "big")
      _b = int.from_bytes(bytes_read[6:], "big")
      if _c == 0:
          result = (0, 0, 0)
      else:
          _s = (_r ** 1.95 + _g ** 2.025 + _b * _b) / 3
          _c = _c ** 0.9
          _r = int(min(_r * _r * _c * 1.576 / _s, 255))
          _g = int(min(_g * _g * _c * 1.576 / _s, 255))
          _b = int(min(_b * _b * _c * 1.576 / _s, 255))
          result = (_r, _g, _b)

    elif (module_type == RADIO_MOTION_SENSOR):
      _ax = int.from_bytes(bytes_read[:2], "big")
      _ay = int.from_bytes(bytes_read[2:4], "big")
      _az = int.from_bytes(bytes_read[4:6], "big")
      _rx = int.from_bytes(bytes_read[6:8], "big")
      _ry = int.from_bytes(bytes_read[8:10], "big")
      _rz = int.from_bytes(bytes_read[10:], "big")
      if (value_index < 6):
        result = (_ax, _ay, _az, _rx, _ry, _rz)[value_index]
      elif (value_index == 7):
        result = math.atan2(_ay, _az) * 180 / math.pi
      else:
        result = math.atan2(_az, _ax) * 180 / math.pi

    elif (module_type == RADIO_HEART_SENSOR):
      _raw = 0
      _pul = 0
      result = (_raw, _pul)[value_index]

    else:
      result = bytes_read

    # Update cache with the new result
    self._update_cache(cache_key, result)
    return result

  def setup_gpio(self, peer, gpio_pin, pin_type):
    gpio_pin = gpio_pin - 11
    self.pin_modes[gpio_pin] = pin_type

    with self.radio:
      self.radio.write(bytes([76 + gpio_pin, peer, pin_type, 0]))

    return

  def read_gpio(self, peer, gpio_pin):
    if gpio_pin < 11 or gpio_pin > 17:
      raise ValueError("GPIO Pin must be between 11 and 17")
    if peer > 10 or peer < 0:
      raise ValueError("Peer number must be between 0 and 10")

    # Create cache key for GPIO reading
    cache_key = f"gpio_{peer}_{gpio_pin}"

    # Return cached data if valid
    if self._is_cache_valid(cache_key):
        return self._get_cached_data(cache_key)

    bytes_read = bytearray(2)
    with self.radio:
      self.radio.write(bytes([(gpio_pin + 72), peer])) # Register for reading GPIO 11 is 83.
      if (peer == 0):
        time.sleep(0.05) # local reads are faster
      else:
        time.sleep(0.2)
      if (peer > 0):
        self.radio.write(bytes([(gpio_pin + 132), 0])) # get the value from the remote sensor
      else:
        self.radio.write(bytes([(gpio_pin + 72), 0])) # get the value from the local sensor
      self.radio.readinto(bytes_read)

    result = int.from_bytes(bytes_read, "big")

    # Update cache with the new result
    self._update_cache(cache_key, result)

    _gpio_mode = self.pin_modes[gpio_pin - 11]
    if (_gpio_mode == RADIO_GPIO_INPUT or _gpio_mode == RADIO_GPIO_INPUT_PULLUP or _gpio_mode == RADIO_GPIO_INPUT_PULLDOWN):
        result = bool(result)
    return result


  def write_gpio(self, peer, gpio_pin, value):
    if gpio_pin < 11 or gpio_pin > 17:
      raise ValueError("GPIO Pin must be between 11 and 17")
    if peer > 10 or peer < 0:
      raise ValueError("Peer number must be between 0 and 10")
    value = min(255, max(0, value))
    with self.radio:
      self.radio.write(bytes([(gpio_pin + 79), peer, value, 0])) # Register for writing GPIO 11 is 90


  def write_motor_module(self, peer, gpio_pin, value):
    reg_addr = 57
    if peer > 10 or peer < 0:
      raise ValueError("Peer number must be between 0 and 10")

    if gpio_pin == 'S1':
        reg_addr = 59
        if (value != 0xFF):
          value = min(180, max(0, value))
    elif gpio_pin == 'S2':
        reg_addr = 60
        if (value != 0xFF):
          value = (min(180, max(0, value)))
    elif gpio_pin == 'M1':
        if (value != 0xFE and value != 0xFF):
          value = min(100, max(-100, value)) + 100
    elif gpio_pin == 'M2':
        reg_addr = 58
        if (value != 0xFE and value != 0xFF):
          value = min(100, max(-100, value)) + 100
    else:
        raise ValueError("Output pin must be 'S1', 'S2', 'M1', or 'M2'")

    with self.radio:
      self.radio.write(bytes([reg_addr, peer, value & 0xFF, 0]))


  # get the address of the radio module
  def get_address(self):
    bytes_read = bytearray(6)
    with self.radio:
      self.radio.write(bytes([0]))
      self.radio.readinto(bytes_read)

    # Fix the byte flipping: swap bytes 0-1, 2-3, and 4-5
    fixed_bytes = bytearray([
      bytes_read[1], bytes_read[0],  # Swap bytes 0 and 1
      bytes_read[3], bytes_read[2],  # Swap bytes 2 and 3
      bytes_read[5], bytes_read[4]   # Swap bytes 4 and 5
    ])

    return self.format_mac_string(fixed_bytes)

  # Set the address for a peer radio module
  def set_peer_address(self, peer, address):
    if peer > 10 or peer < 0:
      raise ValueError("Peer number must be between 0 and 10")
    _addr = bytes(address)
    with self.radio:
      self.radio.write(bytes([peer * 3, 0]) + _addr)
    self.peer_addresses[peer] = self.format_mac_string(_addr)  # Store locally

  # Get peer number from a MAC address using local storage
  def get_peer_from_mac(self, mac_address):
    for peer, mac in self.peer_addresses.items():
      if mac == mac_address:
        return peer
    return None  # Return None if no matching peer is found

  # Get MAC address from a peer number using local storage
  def get_mac_from_peer(self, peer):
    if peer > 10 or peer < 0:
      raise ValueError("Peer number must be between 0 and 10")
    return self.peer_addresses.get(peer, None)  # Return None if peer is not set

  # send a message to one of the radio's peers
  def send_message(self, peer, message):
    if peer > 11 or peer < 0:  # peer 11 = broadcast
      raise ValueError("Peer number must be between 0 and 11")

    # Smart truncation that handles UTF-8 multi-byte characters
    encoded_message = message.encode('utf-8')
    if len(encoded_message) > 110:
        # Truncate byte array and decode back to string to avoid broken UTF-8
        truncated_bytes = encoded_message[:110]
        # Remove any incomplete UTF-8 sequences at the end
        while truncated_bytes and (truncated_bytes[-1] & 0xC0) == 0x80:
            truncated_bytes = truncated_bytes[:-1]
        encoded_message = truncated_bytes

    message_bytes = bytes([REG_RADIO_MSG_SEND, peer])
    message_bytes += encoded_message

    with self.radio:
        self.radio.write(message_bytes)

  # get a message that the radio has received
  def get_message(self):
    bytes_read = bytearray(2)
    with self.radio:
      self.radio.write(bytes([REG_RADIO_MSG_LEN]))
      self.radio.readinto(bytes_read)
    message_len = int.from_bytes(bytes_read, "big")

    if message_len <= 0:
      return ['', -1, '']

    bytes_read = bytearray(message_len)
    with self.radio:
      self.radio.write(bytes([REG_RADIO_MSG_IN]))
      self.radio.readinto(bytes_read)

    message_addr = self.format_mac_string(bytes_read[:6])
    message = 'Error: Unable to read message!'
    try:
      message = bytes_read[6:-1].decode('utf-8')
    except:
      pass

    # Try to get the peer number from the MAC address
    peer = self.get_peer_from_mac(message_addr)
    if peer is None:
      peer = -1  # Unknown peer

    return [message, peer, message_addr]

  # Clear the sensor cache (useful if you want to force fresh readings)
  def clear_cache(self):
    self.sensor_cache.clear()

  # Set a custom cache timeout (in seconds)
  def set_cache_timeout(self, timeout_seconds):
    self.cache_timeout = timeout_seconds

  # Allows for use in context managers.
  def __enter__(self):
    return self

  # Automatically de-initialize after a context manager.
  def __exit__(self, exc_type, exc_val, exc_tb):
    self.deinit()

  # De-initialize the radio.
  def deinit(self):
    self.i2c.deinit()
