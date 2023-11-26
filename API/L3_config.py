# Import the pyeapi library
import pyeapi

# Open a session with leaf1-DC1. The script will find .eapi.conf and reference the credetials automatically.
connect = pyeapi.connect_to('leaf1-DC1')

# "create" sets the port ara Layer 3 port (no switchport)
connect.api('ipinterfaces').create('Ethernet4')

# Set Ethernet4 to the IP address 4.4.4.4 and put the result into the varable (boolean) result
result = connect.api('ipinterfaces').set_address('Ethernet4', '4.4.4.4/24')

# This is just very basic error handling here. It gives a yes or no answer depeding on whether a "200OK" response was given, or another error was generated.
if result:
    print("Completed")
else:
    print("Error!")
