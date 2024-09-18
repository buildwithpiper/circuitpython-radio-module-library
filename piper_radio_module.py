import time
from adafruit_bus_device.i2c_device import I2CDevice

PIPER_RADIO_I2C_ADDR = 0x54
REG_RADIO_SELF_ADDR = 0
REG_RADIO_MSG_LEN = 38
REG_RADIO_MSG_IN = 40
REG_RADIO_MSG_SEND = 42
REG_RADIO_BROADCAST = 44

class piper_radio_module:
  # Initialize the sensor
  def __init__(self, i2c, address=PIPER_RADIO_I2C_ADDR):
    self.radio = I2CDevice(i2c, PIPER_RADIO_I2C_ADDR)

  # format a bytearry into a string representing a MAC address
  def format_mac_string(self, mac_bytes):
    mac_list = list(mac_bytes[:6])
    mac_str = ''.join('{:02x}:'.format(x) for x in mac_list[:5])
    mac_str += '{:02x}'.format(mac_list[-1])
    return mac_str

  # get the address of the radio module
  def get_address(self):
    bytes_read = bytearray(6)
    with self.radio:
      self.radio.write(bytes([0]))
      time.sleep(0.05)
      self.radio.readinto(bytes_read)
    return self.format_mac_string(bytes_read)

  # set the address for a peer radio module
  def set_peer_address(self, peer, address):
    if (peer > 8 or peer < 1):
      peer = 1
    _addr = bytes(address)
    with self.radio:
      self.radio.write(bytes([peer * 3]) + _addr)

  # send a message to one of the radio's peers
  def send_message(self, target, message):
    if (target > 8 or target < 0):
      target = 0
    target = 1 << (target - 1)
    message_bytes = bytes([REG_RADIO_MSG_SEND, target])
    message_bytes += message.encode('utf-8')
    with self.radio:
      self.radio.write(message_bytes)

  # send a message to all radios
  def broadcast_message(self, message):
    message_bytes = bytes([REG_RADIO_BROADCAST])
    message_bytes += message.encode('utf-8')
    with self.radio:
      self.radio.write(message_bytes)

  # get a message that the radio has received
  def get_message(self):
    bytes_read = bytearray(1)
    with self.radio:
      self.radio.write(bytes([REG_RADIO_MSG_LEN]))
      time.sleep(0.05)
      self.radio.readinto(bytes_read)
    message_len = int.from_bytes(bytes_read, "big")

    if message_len <= 0:
      return ['','']

    bytes_read = bytearray(message_len)
    with self.radio:
      self.radio.write(bytes([REG_RADIO_MSG_IN]))
      time.sleep(0.05)
      self.radio.readinto(bytes_read)

    message_addr = self.format_mac_string(bytes_read[:6])
    message = 'Error: Unable to read message!'
    try:
      message = bytes_read[6:-1].decode('utf-8')
    except:
      pass
    return [message, message_addr]

  # Allows for use in context managers.
  def __enter__(self):
    return self

  # Automatically de-initialize after a context manager.
  def __exit__(self, exc_type, exc_val, exc_tb):
    self.deinit()

  # De-initialize the radio.
  def deinit(self):
    self.i2c.deinit()
