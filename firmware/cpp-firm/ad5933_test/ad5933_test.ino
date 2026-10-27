/*
ad5933-test / capacitor bench test
    Reads impedance values from the AD5933 over I2C and prints them serially.

    Baseline: firmware/cpp-firm/ad5933_test from the mjmeli/arduino-ad5933
    sample. Uses the installed library in ~/Arduino/libraries/arduino-ad5933.

    Bench fixture:
      0.1 uF between Drive+ and Drive-
      Sense+ strapped to Drive+, Sense- strapped to Drive-

    ESP32 (Arduino framework): SDA = GPIO21, SCL = GPIO22, 3.3 V logic.
    Power the AD5933 at 3.3 V and connect SDA/SCL directly.

    Single-point capacitor calibration at 50 kHz:
      |Z| = 1 / (2*pi*50kHz*0.1uF) = 31.83 ohm
    REF_IMPEDANCE_OHM is an int, so 32 is used. For a larger signal, change
    START_FREQ to 10000 and REF_IMPEDANCE_OHM to 159 (|Z| = 159.15 ohm).

    The library's frequencySweep() loop has been patched locally to measure
    exactly n points instead of relying on STATUS_SWEEP_DONE, which does not
    complete reliably for a single-point (n == 1) sweep.

    The library does not calibrate phase (upstream TODO); it reports raw I/Q
    and calibrated magnitude.
*/

#include <Wire.h>
#include "AD5933.h"

#define START_FREQ          (50000)
#define FREQ_INCR           (0)
#define NUM_INCR            (0)
#define REF_IMPEDANCE_OHM   (32)

double gain[NUM_INCR+1];
int phase[NUM_INCR+1];

void frequencySweepEasy();
void frequencySweepRaw();

void setup(void)
{
  // Begin I2C. ESP32 needs the bench pins; Mega uses its default 20/21.
#if defined(ARDUINO_ARCH_ESP32)
  Wire.begin(21, 22);
#else
  Wire.begin();
#endif

  // Begin serial output.
  Serial.begin(115200);
  Serial.println("AD5933 Test Started!");

  // Perform initial configuration. Fail if any one of these fail.
  if (!(AD5933::reset() &&
        AD5933::setInternalClock(true) &&
        AD5933::setStartFrequency(START_FREQ) &&
        AD5933::setIncrementFrequency(FREQ_INCR) &&
        AD5933::setNumberIncrements(NUM_INCR) &&
        AD5933::setPGAGain(PGA_GAIN_X1)))
        {
            Serial.println("FAILED in initialization!");
            while (true) ;
        }

  // Perform single-point calibration against the known capacitor.
  if (AD5933::calibrate(gain, phase, REF_IMPEDANCE_OHM, NUM_INCR+1))
    Serial.println("Calibrated!");
  else
    Serial.println("Calibration failed...");
}

void loop(void)
{
  // Easy to use method for frequency sweep.
  frequencySweepEasy();

  // Delay.
  delay(5000);

  // Complex but more robust method for frequency sweep.
  frequencySweepRaw();

  // Delay.
  delay(5000);
}

// Easy way to do a frequency sweep. Does an entire frequency sweep at once and
// stores the data into arrays for processing afterwards. This is easy-to-use,
// but doesn't allow you to process data in real time.
void frequencySweepEasy() {
    // Create arrays to hold the data.
    int real[NUM_INCR+1], imag[NUM_INCR+1];

    // Perform the frequency sweep.
    if (AD5933::frequencySweep(real, imag, NUM_INCR+1)) {
      // Print the frequency data.
      int cfreq = START_FREQ/1000;
      for (int i = 0; i < NUM_INCR+1; i++, cfreq += FREQ_INCR/1000) {
        // Print raw frequency data.
        Serial.print(cfreq);
        Serial.print(": R=");
        Serial.print(real[i]);
        Serial.print("/I=");
        Serial.print(imag[i]);

        // Compute impedance.
        double magnitude = sqrt(pow(real[i], 2) + pow(imag[i], 2));
        double impedance = 1/(magnitude*gain[i]);
        Serial.print("  |Z|=");
        Serial.println(impedance);
      }
      Serial.println("Frequency sweep complete!");
    } else {
      Serial.println("Frequency sweep failed...");
    }
}

// Removes the frequencySweep abstraction from above. This saves memory and
// allows for data to be processed in real time. However, it's more complex.
void frequencySweepRaw() {
    // Create variables to hold the impedance data and track frequency.
    int real, imag, i = 0, cfreq = START_FREQ/1000;

    // Initialize the frequency sweep.
    if (!(AD5933::setPowerMode(POWER_STANDBY) &&          // place in standby
          AD5933::setControlMode(CTRL_INIT_START_FREQ) && // init start freq
          AD5933::setControlMode(CTRL_START_FREQ_SWEEP))) // begin frequency sweep
         {
             Serial.println("Could not initialize frequency sweep...");
             return;
         }

    // Perform the actual sweep. The i guard keeps the single-point case from
    // running past the gain array.
    while (i <= NUM_INCR &&
           (AD5933::readStatusRegister() & STATUS_SWEEP_DONE) != STATUS_SWEEP_DONE) {
        // Get the frequency data for this frequency point.
        if (!AD5933::getComplexData(&real, &imag)) {
            Serial.println("Could not get raw frequency data...");
            break;
        }

        // Print out the frequency data.
        Serial.print(cfreq);
        Serial.print(": R=");
        Serial.print(real);
        Serial.print("/I=");
        Serial.print(imag);

        // Compute impedance.
        double magnitude = sqrt(pow(real, 2) + pow(imag, 2));
        double impedance = 1/(magnitude*gain[i]);
        Serial.print("  |Z|=");
        Serial.println(impedance);

        // Increment the frequency.
        i++;
        cfreq += FREQ_INCR/1000;
        if (i <= NUM_INCR) {
            AD5933::setControlMode(CTRL_INCREMENT_FREQ);
        }
    }

    Serial.println("Frequency sweep complete!");

    // Set AD5933 power mode to standby when finished.
    if (!AD5933::setPowerMode(POWER_STANDBY))
        Serial.println("Could not set to standby...");
}
