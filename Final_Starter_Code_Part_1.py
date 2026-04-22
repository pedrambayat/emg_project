'''
backbone comes from https://stackoverflow.com/questions/67172127/real-time-plotting-of-ble-data-using-bleak-and-pyqtgraph-packages
'''
import sys
import asyncio
from PyQt5 import uic
from PyQt5.QtWidgets import QWidget,QApplication
import numpy as np
from bleak import BleakScanner, BleakClient
from bleak.backends.characteristic import BleakGATTCharacteristic

import qasync

from sys import platform
"""
Patch for windows 10 error 
"""
if platform == "win32":
    try:
        from bleak.backends.winrt.util import allow_sta
        # tell Bleak we are using a graphical user interface that has been properly
        # configured to work with asyncio
        allow_sta()
    except ImportError:
        # other OSes and older versions of Bleak will raise ImportError which we
        # can safely ignore
        pass
    """
    end patch for windows 10 error
    """

# BLE peripheral ID
ADDRESS = "10:52:1C:5F:BE:EA" # EDIT THIS VARIABLE MAC ADB7175A-EA74-39E6-0F89-5B7EDC7FBC3D | Windows B0:B2:1C:57:5B:EE

'''DO NOT EDIT ANYTHING BELOW THIS for Part 1'''
# UART_CHAR_UUID = "34E49D7D-23F4-49FA-F025-CE6578F447B1"
UART_CHAR_UUID = "5212ddd0-29e5-11eb-adc1-0242ac120002"

qtDesignerFile = "simple_GUI.ui" # Enter your filename here.


class MyApp(QWidget):
    """Class for my GUI application to interface with an Arduino MKR1010

    Args:
        QWidget (QWidget): parent class
    """
    def __init__(self):
        """
        This is a standard function for any class in python and gets called when you create an instance/variable of this class type
        """
        super().__init__() # again this is a standard call to the parent class' (in this cas QWidget) __init__ method to make sure it has all the necessary parameters

        # initial variables for bluetooth
        self._client = None         # the connection to Bluetooth Low Energy (BLE) device in order to query and control it
        self._storedData = []       # the data acquired from the BLE Device. This data will eventually be a list of lists each with 50 points
        self._device = None         # the BLE device

        # GUI Set up
        self.resize(640, 480)
        self.init_UI()

    def init_UI(self):
        # establish main UI
        uic.loadUi(qtDesignerFile, self)

        # setup up plot
        self.graphWidget = self.graphicsView.addPlot(title="EMG Data")
        self.graphWidget.setLabel(axis="left", text="Bit Value (max 255)")
        self.graphWidget.setLabel(axis="bottom", text="Points")               
        self._curve = self.graphWidget.plot(self._storedData)   # reference to the line object i.e. the plot of the data

        #connect push buttons
        self.connectButton.clicked.connect(self.handle_connect)
        self.streamButton.clicked.connect(self.handle_stream)
        self.stopButton.clicked.connect(self.handle_stop)


    """Property setters and getters if you add an additional protected variable you will need to add a setter and getter method for it"""
    @property
    def device(self):
        return self._device
    

    @device.setter
    def device (self,newDevice):
        self._device = newDevice


    @property
    def client(self):
        return self._client
    

    @client.setter
    def client (self,newClient):
        self._client = newClient


    @property
    def storedData(self):
        return self._storedData


    @storedData.setter
    def storedData(self,newData):
        self._storedData = newData
    

    @property
    def curve(self):
        return self._curve
    

    @curve.setter
    def curve(self,newCurve):
        self._curve = newCurve

    async def build_client(self):
        """
        builds and connects the client to handle BLE communication between the computer and the device
        If an existing client already exists then the preexisting client is deleted before the new one is created.
        """
        if self.client is not None:
            await self.client.stop()
        self.client = BleakClient(self.device)
        await self.client.connect()


    # The @qasync.asyncSlot() is used to help connect this method to a button press in the GUI
    @qasync.asyncSlot()
    async def handle_connect(self):
        """
        Runs when the connect button is pressed in the GUI.
        Calls the scan_for_device method to scan for the user's BLE device.
        Calls the build_client method to establish the BLE connection between the Computer and the device
        Alters the user to a successful connection

        The @qasync.asyncSlot() is used to indicate that this method is a direct callback from the GUI
        """
        self.log.setText("scanning for device...")
        self.device = await BleakScanner.find_device_by_address(ADDRESS)
        self.log.setText("Connecting to device...")
        await self.build_client()
        self.log.setText("Connected") 
 
      
    # The @qasync.asyncSlot() is used to help connect this method to a button press in the GUI
    @qasync.asyncSlot()    
    async def handle_stream(self):
        """
        Runs when the stream button is pressed in the GUI.
        Starts processing notifications from the BLE device with the notification_handler function
        """
        await self.client.start_notify(UART_CHAR_UUID, self.notification_handler)


    # The @qasync.asyncSlot() is used to help connect this method to a button press in the GUI
    @qasync.asyncSlot()
    async def handle_stop(self):
        """
        Runs when the stop button is pressed in the GUI.
        Stops processing notifications from the BLE device.
        Disconnects from the BLE Device
        """
        if self.client is not None:
            await self.client.stop_notify(UART_CHAR_UUID)
            await self.client.disconnect()
        self.client = None
        self.log.setText('Device was disconnected.')


    def notification_handler(self,characteristic: BleakGATTCharacteristic, data: bytearray):       
        """
        Simple notification handler.
        Converts the incoming stream of data (50 points) from a bytearray to an integer array.
        Calls the update_plot method to append the converted data to storedData list and updates the plot with the most recent data stream
        With the default arduino script this should be called every 50ms

        Args:
            characteristic (BleakGATTCharacteristic): the GATTCharacteristic of interest
            data (bytearray): the data attached to the notification. In this case it is a 50 point array 
        """
        convertData = list(data)
        self.update_plot(convertData)

    
    def update_plot(self, vals):
        """
        Appends the new values to storedData (creating a list of 50 point lists).
        Updates the plot of the GUI with the most recent data steam

        Args:
            vals (lint (int)): the newest set of 50 points
        """
        self.storedData.append(vals)
        plotData= np.ravel(self.storedData[-5:])  # unpacks the list of lists into one list 
        self.curve.setData(plotData)

    
    def closeEvent(self, event):
        """
        Called whenever the user manually or force quits the application.
        Will disconnect from the BLE device and will terminate any async tasks
        """
        self.handle_stop()
        super().closeEvent(event)
        for task in asyncio.all_tasks():
            task.cancel()


def main(args):
    """This is the main method that gets executed when the script is called.
    It wil create an QApplication to run the GUI.

    You should not edit anything in this method, without speaking to the teaching staff

    Args:
        args: any additional arguments the user passes to the script (this is only here by convention)
    """
    app = QApplication(sys.argv)
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    a = MyApp()
    a.show()
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main(sys.argv)
    # await main(sys.argv)  # for jupyter notebooks
