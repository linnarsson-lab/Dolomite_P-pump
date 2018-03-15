import serial
from serial.tools import list_ports
import time
import struct
import warnings


def find_address(identifier = None):
    """
    Find the address of a serial device. It can either find the address using
    an identifier given by the user or by manually unplugging and plugging in 
    the device.
    Input:
    `identifier`(str): Any attribute of the connection. Usually USB to Serial
        converters use an FTDI chip. These chips store a number of attributes
        like: name, serial number or manufacturer. This can be used to 
        identify a serial connection as long as it is unique. See the pyserial
        list_ports.grep() function for more details.
    Returns:
    The function prints the address.
    `port`(obj): Retruns a pyserial port object. port.device stores the 
        address.
    
    """
    found = False
    if identifier != None:
        port = [i for i in list(list_ports.grep(identifier))]
        
        if len(port) == 1:
            print('Device address: {}'.format(port[0].device))
            found = True
        elif len(port) == 0:
            print('''No devices found using identifier: {}
            \nContinue with manually finding USB address...\n'''.format(identifier))
        else:
            for p in connections:
                print('{:15}| {:15} |{:15} |{:15} |{:15}'.format('Device', 'Name', 'Serial number', 'Manufacturer', 'Description') )
                print('{:15}| {:15} |{:15} |{:15} |{:15}\n'.format(str(p.device), str(p.name), str(p.serial_number), str(p.manufacturer), str(p.description)))
            raise Exception("""The input returned multiple devices, see above.""")

    if found == False:
        print('Performing manual USB address search.')
        while True:
            input('    Unplug the USB. Press Enter if unplugged...')
            before = list_ports.comports()
            input('    Plug in the USB. Press Enter if USB has been plugged in...')
            after = list_ports.comports()
            port = [i for i in after if i not in before]
            if port != []:
                break
            print('    No port found. Try again.\n')
        print('Device address: {}'.format(port[0].device))
    
    return port[0]

class P_pump():
    """
    Control the Dolomite Mitos P-pump, a pressure pump used for microfluidic 
    applications. 
    Getting started:
    Connect the pump using the supplied USB to serial converter and find the
    address of the port using the "find_address()" function. Initiate the pump
    by calling this class and providing the address. It is advised to tare the 
    pump before each operation; use the "tare_pump()" function.
    The pump can either be operated in pressure control mode, or flow control
    mode. In pressure control mode, you set a pressure and the pump tries to 
    keep that pressure. If a flow sensor is installed, you can control the 
    flow rate directly.     
    Use the "set_pressure()" and "set_flow()" functions to pump with a 
    specified pressure or speed and with the option to control the duration
    of the operation.
    The pump can more finely be controled by calling the individual control 
    set functions. 
    Errors are always printed, other output can be toggled ON or OF using the
    verbose option. 
    
    """
    
    def __init__(self, address, name=[], pump_id=0, verbose=True):
        """
        Input:
        `address`(str): Address of the P-pump. '/dev/ttyUSBX' on linux or 'COMX'
            on windows. Use the "find_address" function to find the address of 
            your device. 
        `name`(str): Optional, name to identify the P-pump for the user.
        `pump_id`(int): If multiple P-pumps are connected, please provide the 
            unique pump address. If pump_id is 0, the command will be accepted
            by all connected pumps.
        `verbose`(bool): Set to True to print extra output about the pump
            operation.

        """
        self.address = address
        self.name = name
        self.pump_id = pump_id
        self.verbose = verbose
        self.verboseprint = print if verbose else lambda *a, **k: None
        self.ser = serial.Serial(address, timeout=2, baudrate=115200,
                                 bytesize=serial.EIGHTBITS,
                                 stopbits=serial.STOPBITS_ONE,
                                 parity=serial.PARITY_NONE)
        
    #_COMMUNICATION_WITH_THE_PUMP_____________________________________________
    def message_builder(self, message_type, location, value=0, pump_id=None):
        """
        Construct a command message for the pump.
        Input:
        `message_type`(int): 1 to write a message to the pump. 2 to read a value
            from the pump.
        `location`(int): Address of the value to be written/read in the pump.
        `value`(int): Value to be written
        `pump_id`(int): Unique identifier of the pump. Use 0 to target all 
            connected pumps.            

        """
        message = bytearray(b'\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        if pump_id == None:
            pump_id = self.pump_id
        message[1] = pump_id
        message[2] = message_type
        if message_type == 1 or message_type == 2:
            message[4] = location
        message[-4:] = struct.pack('>i', value)

        #Add checksum: bitwise exclusive OR of all other bits.
        checksum = 0
        for b in message:
            checksum ^= b
        message.append(checksum)

        return bytes(message)
    
    def send_message(self, message):
        """
        Send a message to the pump. The message needs to be a 12 bit byte
        formatted by the message_builder() function. 

        """
        #Make sure no message is already waiting to be read
        self.ser.read_all()
        #Write message
        self.ser.write(message)
        time.sleep(0.1)

        #check if message is received after command is sent.
        if message[2] != 2:
            self.check_ok()
            
    def read_message(self):
        """
        Read a 12bit message from the pump. Returns one byte. 

        """
        try:
            response = self.ser.read(12)
        except Exception:
            self.verboseprint('No message send by pump. No message to read')

        return response

    def interpret_message(self, response):
        """
        Interpret the response of the pump. Prints the interpretation and returns
        True if the message contains no error code. 
        
        """
        if response[2] == 1:
            response_message = (response[7] * (256**3)) + (response[8] * (256**2)) + (response[9] * 256) + response[10]
            print('{}: Read request response: {}'.format(self.name, response_message))
            print('{}: Pump response: {}'.format(self.name, str(response)))
            return True
        elif response[2] == 2:
            return True
        elif response[2] == 3:
            if response[3] == 1:
                print('{}: Checksum error'.format(self.name))
            elif response[3] == 2:
                print('{}: Command unknown'.format(self.name))
                print('{}: Pump response: {}'.format(self.name, str(response)))
            elif response[3] == 3:
                print('{}: Invalid data, out of range address of value'.format(self.name))
                print('{}: Pump response: {}'.format(self.name, str(response)))
            else:
                print('{}: Timeout, Communications timeout failure'.format(self.name))
                print('{}: Pump response: {}'.format(self.name, str(response)))
            return False
        elif response[2] == 4:
            print('{}: Firmware version: {}'.format(self.name, str(response[3]), str(response[4]), str(response[5]), str(response[6])))
            return True
        else:
            print('{}: Unidentifiable message type'.format(self.name))
            return False
        
    def check_ok(self):
        """
        If the pump is given a command it will acknowledge it. This function
        returns True if the pump confirmed the command and False if it did not
        send a message back. Note that this function does not read back the
        written value. 

        """
        response = self.read_message()
        try:
            if self.interpret_message(response) == True:
                return True
            else:
                warnings.warn('{}: Pump error'.format(self.name))
                self.interpret_message(response)
        except Exception:
            warnings.warn('{}: No pump response'.format(slef.name))

            return False
        
    #_GET_METHODS_____________________________________________________________    
    def get_mode(self):
        """
        Get the mode of the pump. 
        Returns mode:
            0 = Pump idle
            1 = Pump in Control mode (pumping)
            2 = Pump performing tare
            3 = Error. (function prints the specific error code)
            4 = Pump performing leak test

        """
        self.send_message(self.message_builder(2,81))

        mess = self.read_message()
        translate = struct.unpack('12B', mess)
        mode = translate[-2]

        if mode == 3: #pump error
            self.send_message(self.message_builder(2,82))
            error_mess = struct.unpack('12B', self.read_message())[-2]
            error_values = {
                1 : 'Supply > maximum pressure',
                2 : 'Tare: timed out',
                3 : 'Tare: Supply still connected',
                4 : 'Control start timed out. Opening valves, but chamber pressure unchanged',
                5 : 'Target too low',
                6 : 'Target too high',
                7 : 'Leak test: supply pressure too low',
                8 : 'Leak test: time out if the pressure cannot reach target',
                9 : 'Flow sensor lost during flow control',
            }
            self.set_idle()
            print('{}: Pump error encountered, pump set to idle.'.format(self.name))
            raise Exception(error_values[error_mess])

        return translate[-2]

    def get_control_type(self):
        """
        Check if the pump is into "Pressure" control mode (0).
        Or if it in in "Flow" control mode (1).
        Returns:
            control type (int): Zero for Pressure control, One for Flow control. 

        """
        self.send_message(self.message_builder(2,77))
        response = self.read_message()
        return int.from_bytes(response[-2:-1], byteorder='big', signed=False)
    
    def get_target(self):
        """
        Get the target flow rate or pressure.

        """
        self.send_message(self.message_builder(2,79))
        response = self.read_message()
        return int.from_bytes(response[-5:-1], byteorder='big', signed=False)
    
    def get_sensor(self):
        """
        Get the type of the installed flow sensor.
        Returns the model number, flow rate range and the unit.

        """
        self.send_message(self.message_builder(2,88))
        response = self.read_message()
        sensor = int.from_bytes(response[-5:-1], byteorder='big', signed=False)
        sensor_types = {
            0: 'None connected',
            1: 'LG16-0025, 0.07-1.5ul/min, unit=ul/min',
            2: 'LG16-0150, 0.4-7ul/min, unit=ul/min',
            3: 'LG16-0480, 1-50ul/min, unit=ul/min',
            4: 'LG16-1000, 30-1000ul/min, unit=ul/min',
            5: 'LG16-2000, 200-5000ul/min, unit=ml/min',
            }
        return sensor_types[sensor]

    def get_temp(self):
        """
        Returns the temperature in Celsius of the Atmospheric, Supply and Chamber
        pressure sensors, in that order. 
        Returns:
            temperatures(list): Temperatures of the Atmospheric, supply and Chamber
            pressure sensors.

        """
        #Temperature of Atmospheric pressure sensor
        self.send_message(self.message_builder(2,67))
        response = self.read_message()
        atm = int.from_bytes(response[-5:-1], byteorder='big', signed=False)/10

        #Temperature of Supply pressure sensor
        self.send_message(self.message_builder(2,68))
        response = self.read_message()
        supp = int.from_bytes(response[-5:-1], byteorder='big', signed=False)/10

        #Temperature of Chamber pressure sensor
        self.send_message(self.message_builder(2,69))
        response = self.read_message()
        cham = int.from_bytes(response[-5:-1], byteorder='big', signed=False)/10

        return [atm, supp, cham]
    
    def get_pressure(self):
        """
        Returns the pressure of the Atmospheric, Supply and Chamber
        pressure sensors, in that order. Note the units. Gauge means relative to
        atmospheric pressure. 
        Returns:
            temperatures(list): Temperatures of the Atmospheric (mbar),
            supply(mbar gauge) and Chamber(mbar gauge) pressure sensors.

        """

        #Pressure of Atmospheric pressure sensor
        self.send_message(self.message_builder(2,64))
        response = self.read_message()
        atm = int.from_bytes(response[-5:-1], byteorder='big', signed=False)/10

        #Pressure of Supply pressure sensor
        self.send_message(self.message_builder(2,65))
        response = self.read_message()
        supp = int.from_bytes(response[-5:-1], byteorder='big', signed=False)

        #Pressure of Chamber pressure sensor
        self.send_message(self.message_builder(2,66))
        response = self.read_message()
        cham = int.from_bytes(response[-5:-1], byteorder='big', signed=False)

        return [atm, supp, cham]
    
    
    #_SET_METHODS_____________________________________________________________
    def start_flow(self):
        """
        Set the pump into Control mode. Meaning that it will start pumping using 
        the target flow or pressure value.

        """
        counter = 0
        while True:
            self.send_message(self.message_builder(1,78,1))      
            if self.get_mode()  == 1:
                self.verboseprint('{}: Pump set to control mode, starting flow'.format(self.name))
                break
            else:
                counter += 1
                print(counter)
                if counter > 5:
                    self.set_idle()
                    print('{}: Could not set pump to control mode, checking for errors:'.format(self.name))
                    if self.get_mode() == 0:
                        print('{}: No pump errors'.format(self.name))
                    raise Exception("Stopped: pump error.")
                    
    def set_idle(self):
        """
        Set the pump in idle state. This will vent the chamber and stop the flow.

        """
        counter = 0
        while True:
            self.send_message(self.message_builder(1,78,0))
            if self.get_mode() == 0:
                self.verboseprint('{}: Pump set to idle'.format(self.name))
                break
            else:
                counter += 1
                if counter > 5:
                    print('{}: Could not set pump to idle, checking for errors:'.format(self.name, target))
                    if self.get_mode() == 0:
                        print('{}: No pump errors'.format(self.name))
                    raise Exception("Stopped: pump error.")
                    
    def set_target(self, target):
        """
        Set the flow or pressure target of the pump. 
        Input:
        `target`(int): Target flow speed (picoliter/second) or pressure 
            (mbar gauge) gauge means above atmospheric. 

        """        
        counter = 0
        while True:
            self.send_message(self.message_builder(1,79,target))
            if target == self.get_target():
                self.verboseprint('{}: Pump target set to {} pl/s'.format(self.name, target))
                break
            else:
                counter += 1
                if counter > 5:
                    self.set_idle()
                    print('{}: Could not set pump to target flow/pressure, target = {}, checking for errors:'.format(self.name, target))
                    if self.get_mode() == 0:
                        print('{}: No pump errors'.format(self.name))
                    raise Exception("Stopped: pump error.")
    
    def set_flow_control(self):
        """
        Set the pump into flow control mode.
        This does not start the pump, use "start_flow()" to start pumping.

        """
        counter = 0
        while True:
            self.send_message(self.message_builder(1,77,1))
            if self.get_control_type() == 1:
                self.verboseprint('{}: Pump set to Flow control mode'.format(self.name))
                break
            else:
                counter += 1
                if counter > 5:
                    self.set_idle()
                    print('{}: Could not set pump to Flow control, checking for errors:'.format(self.name))
                    if self.get_mode() == 0:
                        print('{}: No pump errors'.format(self.name))
                    raise Exception("Stopped: pump error.")

    def set_pressure_control(self):
        """
        Set the pump in Pressure control mode.
        This does not start the pump, use "start_flow()" to start pumping.

        """
        counter = 0
        while True:
            self.send_message(self.message_builder(1,77,0))
            if self.get_control_type() == 0:
                self.verboseprint('{}: Pump set to Flow control mode'.format(self.name))
                break
            else:
                counter += 1
                if counter > 5:
                    self.set_idle()
                    print('{}: Could not set pump to Flow control, checking for errors:'.format(self.name))
                    if self.get_mode() == 0:
                        print('{}: No pump errors'.format(self.name))
                    raise Exception("Stopped: pump error.")
                    
                    
    #_HIGHER_LEVEL_FUNCTIONS__________________________________________________
    def tare_pump(self):
        """
        Tare the pump to the current atmospheric pressure. Advised to perform
        before each operation. 

        """
        print('''\nTaring pump {}:\n
            Please disconnect the air supply and open pump chamber.\n
            Make sure there is not flow in the system.'''.format(self.name))
        input('Press Enter when ready for tare...')
        self.send_message(self.message_builder(1,78,2))
        print('Performing tare. Expected duration ~15seconds')
        while True:
            time.sleep(1)
            if self.get_mode() == 0:
                break
        print('Performed pump {} tare.'.format(self.name))

    def set_flow(self, speed, unit='pl/s', hold='00:00:00:00'):
        """
        Start pump in flow control mode with the target flow rate. Can pump for
        a specified time. Progam will sleep until operation is finished.
        Input:
            `speed`(int): Flow rate to pump with
            `unit`(str): The unit of the target flow rate. Options: 
                ['pl/s', 'pl/m', 'nl/s', 'nl/m', 'ul/s', 'ul/m', 'ml/s', 'ml/m']
                Default = 'pl/s'
            `hold`(str): Time to hold the target pressure, in the format:
                'dd:hh:mm:ss'. Defaults to indefinite hold until next command. 
                Use the "set_idle()" function to stop the flow. 

        """
        #Set pump in flow control mode
        self.set_flow_control()

        #Convert flow speed to pl/second
        conversion = {
        'pl/s' : 1,
        'pl/m' : (1/60),
        'nl/s' : 1000,
        'nl/m' : (1000/60),
        'ul/s' : 1000000,
        'ul/m' : (1000000/60),
        'ml/s' : 1000000000,
        'ml/m' : (1000000000/60)
        }
        if unit not in conversion.keys():
            raise ValueError('{}: {} is not a valid unit. Choose from: {}'.format(self.name, unit, conversion.keys()))
        #Calculate speed in picoliter/second    
        speed = int(speed * conversion[unit])
        #Set flow speed
        self.set_target(speed)

        if hold == '00:00:00:00':
            self.verboseprint('{}: Start flow with indefinite hold'.format(self.name))
            self.start_flow()
        else:
            time_filt = [86400,3600,60,1]
            total_time = sum([a*b for a,b in zip(time_filt, map(int,hold.split(':')))])
            self.verboseprint('{}: Flow set, Will pump for: {}'.format(self.name, hold))
            self.start_flow()
            time.sleep(total_time)
            self.verboseprint('    Pumped for {}'.format(hold))
            self.set_idle()
            
    def set_pressure(self, pressure, hold='00:00:00:00'):
        """
        Start pump in pressure control mode with the target pressure. Can pump for
        a specified time. Program will sleep until operation is finished. 
        Input:
            `pressure`(int): Target pressure in mbar gauge (gauge = difference with
                atmospheric)
            `hold`(str): Time to hold the target pressure, in the format:
                'dd:hh:mm:ss'. Defaults to indefinite hold until next command. 
                Use the "set_idle()" function to stop the flow.

        """
        #Set pump in pressure control mode
        self.set_pressure_control()

        #Set flow speed
        self.send_message(self.message_builder(1,79,pressure))

        if time == '00:00:00:00':
            self.verboseprint('{}: Start pressure with indefinite hold'.format(self.name))
            self.start_flow()
        else:
            time_filt = [86400,3600,60,1]
            total_time = sum([a*b for a,b in zip(time_filt, map(int,hold.split(':')))])
            self.verboseprint('{}: Pressure set, Will pump for: {}'.format(self.name, hold))
            self.start_flow()
            time.sleep(total_time)
            self.verboseprint('    Pumped for {}'.format(hold))
            self.set_idle()

if __name__ == "__main__":
	find_address()
