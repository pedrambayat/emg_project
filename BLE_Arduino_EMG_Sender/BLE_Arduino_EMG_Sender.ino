/*
    Michael Patterson
  Sender Arduino for EMG signal collection

  References

   For the basis of the union multi_reading_data data type
    https://forum.arduino.cc/index.php?topic=659562.32

   This code was adapted from the built-in example in the ArduinoBLE library
   ArduinoBLE > Peripheral > BatteryMonitor
*/

#include <ArduinoBLE.h>

///////////////////////////////////////////// EDITABLE REGION ///////////////////////////////////////////////

//Establish the students penn key to be used in the device and local names of the BLE peripheral
char pennKey[]                  =           "pbayat";                       // a short unique identifier

// Hardware-filtered EMG thresholds for the Morse control state.
// When the filtered signal rises above CONTROL_ON_THRESHOLD the control state becomes pressed.
// It stays pressed until the signal falls below CONTROL_OFF_THRESHOLD.
const byte CONTROL_ON_THRESHOLD  =           150;
const byte CONTROL_OFF_THRESHOLD =           135;
const uint16_t CONTROL_ON_HOLD_MS  =         15;
const uint16_t CONTROL_OFF_HOLD_MS =         25;

///////////////////////////////////////// END EDITABLE REGION ///////////////////////////////////////////////

// The portions of the device and local names which will be combined with pennKey
char nameD[]                    =           "MKR1010_";
char nameL[]                    =           "EMG_Sender_";

BLEDescriptor charDescriptor("2901", "EMG Data");
BLEDescriptor controlDescriptor("2901", "EMG Control State");


// Establish Sampling with desired 1kHz Sample Rate
const uint32_t SAMPLE_RATE        =           1000;                         // Hz 1000
const uint32_t UPDATE_INTERVAL    =           50000;                        // uS time to send small packets of data 50000
const uint32_t SAMPLE_PD          =           1000000 / SAMPLE_RATE;        // uS how often to take a new sample aka the sample period
const uint32_t NUMBER_OF_READINGS =           UPDATE_INTERVAL / SAMPLE_PD;  // number of samples in the small packet required for desired SAMPLE_RATE with given UPDATE_INTERVAL
const uint16_t CONTROL_ON_HOLD_SAMPLES  =     (CONTROL_ON_HOLD_MS * SAMPLE_RATE + 999) / 1000;
const uint16_t CONTROL_OFF_HOLD_SAMPLES =     (CONTROL_OFF_HOLD_MS * SAMPLE_RATE + 999) / 1000;

// Establish constant pins
const int ledPin                  =           LED_BUILTIN;              // Establish LED pin for altering user of BLE Status
const int readPin                 =           A3;                       // Establish the analogRead pin as A6

/*
   BLE UUIDs
   These are used to communicate how/what kind of data is being sent over bluetooth.
   Different types of device will have standard UUIDs so that anything it would interface with would know how to process its data
   Since we are using a custom device these UUIDs were randomly generated from https://www.uuidgenerator.net/
*/

char BLE_UUID_SENSOR_SERVICE[]           =             "386a83e2-28fa-11eb-adc1-0242ac120002";
char BLE_UUID_SENSOR_CHAR[]              =             "5212ddd0-29e5-11eb-adc1-0242ac120002";
char BLE_UUID_CONTROL_CHAR[]             =             "5212ddd1-29e5-11eb-adc1-0242ac120002";

//creating new data type multi_reading_data to store multiple readings in an array like structure
union multi_reading_data
{
  struct __attribute__( ( packed ) )
  {
    byte values[NUMBER_OF_READINGS];
  };
  byte bytes[ NUMBER_OF_READINGS * sizeof( byte ) ];
};

union multi_reading_data multiReadingData;

// create the BLE objects
BLEService sensorService( BLE_UUID_SENSOR_SERVICE );
BLECharacteristic sensorChar( BLE_UUID_SENSOR_CHAR, BLERead | BLENotify, sizeof multiReadingData.bytes );
BLECharacteristic controlChar( BLE_UUID_CONTROL_CHAR, BLERead | BLENotify, 1 );

uint32_t i = 0;                                                         // index location of the next element to add to the multi_reading_data array
byte controlState = 0;
uint16_t controlOnSamples = 0;
uint16_t controlOffSamples = 0;

void updateControlState(byte analogValueByte)
{
  if (!controlState)
  {
    if (analogValueByte >= CONTROL_ON_THRESHOLD)
    {
      controlOnSamples++;
      if (controlOnSamples >= CONTROL_ON_HOLD_SAMPLES)
      {
        controlState = 1;
        controlOnSamples = 0;
        controlOffSamples = 0;
        controlChar.writeValue(&controlState, 1);
      }
    }
    else
    {
      controlOnSamples = 0;
    }
    return;
  }

  if (analogValueByte < CONTROL_OFF_THRESHOLD)
  {
    controlOffSamples++;
    if (controlOffSamples >= CONTROL_OFF_HOLD_SAMPLES)
    {
      controlState = 0;
      controlOnSamples = 0;
      controlOffSamples = 0;
      controlChar.writeValue(&controlState, 1);
    }
  }
  else
  {
    controlOffSamples = 0;
  }
}

void setup()
{
  // Divide Clock by 64 to speed up sampling rate | set deafult read to 8 bits resolution for MKR WiFi 1010 controller only!!
  ADC->CTRLB.reg = ADC_CTRLB_PRESCALER_DIV64 | ADC_CTRLB_RESSEL_8BIT;

  // initialize the built-in LED pin to indicate when a BLE setup was successful
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, LOW);
  setupBLE(nameD, nameL);
}

void loop()
{
  uint32_t tStart = micros();                                         // us; start time

  // listen for BLE peripherals to connect:
  BLEDevice central = BLE.central();
  if ( central )
  {
    // turn off built in LED to indicate a found connection
    digitalWrite(ledPin, LOW);
    while ( central.connected() )
    {
      if ( central.rssi() != 0 )  // there is a connection
      {
        // Only take a reading once per SAMPLE_PD
        uint32_t tNow = micros(); // ms; time now
        if (tNow - tStart >= SAMPLE_PD)
        {
          tStart += SAMPLE_PD; // reset start time to take next sample at exactly the correct pd
          byte analogValueByte = analogRead(readPin);
          updateControlState(analogValueByte);
          multiReadingData.values[i] = analogValueByte;
          i++;
          if (i >= NUMBER_OF_READINGS)
          {
            i = 0; // reset to beginning of array, so you don't try to save readings outside of the bounds of the array
            sensorChar.writeValue( multiReadingData.bytes, sizeof multiReadingData.bytes );
          }
        }
      }
    }
    //when the central disconnects, turn on the indicator light to indicate that device is searching for central:
    digitalWrite(ledPin, HIGH);
    // // Re-start advertising after disconnection
    // BLE.advertise();
  }
}

// Function definitions
void setupBLE(char* nameD, char* nameL)
{
  /*
     Sets up the arduino as a BLE Peripheral with the input device and local name
     and the previously defined sensorService with an initial value of 0.
     After completing these actions it advertise the Peripheral

     If it fails to initialize the BLE library the Built-in LED will blink
     indicating that the user needs to reset the Arduino to try again

     If it is successful then the built-in LED will remain solid to indicate it is
     polling for a central connection

     nameDevice --> char array containing the desired device name
     nameLocal --> char array containing the desired local name
  */
  //initialize BLE library
  if (!BLE.begin())
  {
    while (1)
    {
      //Blink the built-in LED to alert the user
      digitalWrite(ledPin, HIGH);
      delay(100);
      digitalWrite(ledPin, LOW);
      delay(100);
    }
  }

  // The Device Name can be advertised on iOS
  char nameDevice[sizeof(nameD) + sizeof(pennKey) + 1];
  sprintf(nameDevice, "%s%s", nameD, pennKey);
  BLE.setDeviceName(nameDevice);

  // The LocalName is what gets advertised
  char nameLocal[sizeof(nameL) + sizeof(pennKey) + 1];
  sprintf(nameLocal, "%s%s", nameL, pennKey);
  BLE.setLocalName(nameLocal);

  BLE.setAdvertisedService(sensorService);

  // BLE add characteristics
  sensorService.addCharacteristic(sensorChar);
  sensorChar.addDescriptor(charDescriptor);
  sensorService.addCharacteristic(controlChar);
  controlChar.addDescriptor(controlDescriptor);

  // add service
  BLE.addService(sensorService);

  // set the initial value for the characteristic:
  sensorChar.writeValue( multiReadingData.bytes, sizeof multiReadingData.bytes );
  controlChar.writeValue( &controlState, 1 );

  // start advertising
  BLE.advertise();

  // turn on built in LED to indicate a successful BLE setup
  digitalWrite(ledPin, HIGH);
}
