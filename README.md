# Dolomite Mitos P-pump control
Python control for the Dolomite Mitos P-pump, a pump used in microfluidic applications.

Control the [Mitos P-Pump](https://www.dolomite-microfluidics.com/product/mitos-p-pump/) from Dolomite, using serial communication.  
Possible to use the pump in flow control mode or pressure control mode, and program a script to automate liquid dispensing.  

## Citation
If you use this code in a scientific publication please cite the following paper: https://doi.org/10.1101/276097

## Dependencies:
[pyserial](https://pypi.python.org/pypi/pyserial)
To install run: ```pip install pyserial```

## Getting started:
Import the module
```python
import Py_P_Pump
```
Find the address where the pump is mounted on your computer.
```python
Py_P_Pump.find_address()
```
OR if you use the Dolomite USB to Serial cable, or know the ID of the FTDI chip:
```python
Py_P_Pump.find_address(identifier='Dolomite')
```
This prints the address: '/dev/ttyUSBX' on unix, or 'COMX' on Windows. Use this address to initiate the pump:
```python
my_pump = Py_P_Pump.P_pump(address, name='Pump_1', pump_id=0, verbose=True)
```
If you are on linux and get a "Permission denied" error. Run the following command in the terminal first with the correct address:
```bash
sudo chmod 666 '/dev/ttyUSBX'
```  

## Pump operation:
First perform a tare of the pump. Run the following command and follow the instructions.
```python
my_pump.tare_pump()
```
The pump can be operated in pressure control mode or in flow control mode. To start pressure control and start pumping with 100 mbar for 1 minute and 5 seconds, run:
```python
my_pump.set_pressure(100, hold='00:00:01:05')
```
To operate the pump in flow control mode and pump with a speed of 2 ul/s untill a stop command is send, run:
```python
my_pump.set_flow(2, unit='ul/s', hold='00:00:00:00')
```
To stop the pump, run:
```python
my_pump.set_idle()
```

## Non-supported functions:
In this implementation it is not possible to: stream data, set liquid type and perform leak test.
