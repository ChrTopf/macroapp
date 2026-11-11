const int BUTTON_PIN = 0;
const int LED_PIN = 2;

// Index of this button; serial_keyboard.py maps it to the key to press.
const int KEY_INDEX = 1;

const unsigned long DEBOUNCE_DELAY = 50;
const unsigned long STARTUP_DELAY = 2000;

bool lastButtonState = HIGH;
bool buttonState = HIGH;
unsigned long lastDebounceTime = 0;

void setup() {
  Serial.begin(9600);

  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);

  digitalWrite(LED_PIN, HIGH);
}

void loop() {
  int reading = digitalRead(BUTTON_PIN);

  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }

  if ((millis() - lastDebounceTime) > DEBOUNCE_DELAY) {
    if (reading != buttonState) {
      buttonState = reading;

      if (buttonState == LOW) {
        digitalWrite(LED_PIN, HIGH);

        Serial.print("KEY:");
        Serial.println(KEY_INDEX);

        digitalWrite(LED_PIN, LOW);
      }
    }
  }

  lastButtonState = reading;
}