# UART to MQTT
Jest to proxy/most pomiędzy interfejsem UART i komendami AT a protokołem MQTT. Pozwala na komunikację z urządzeniami za pomocą MQTT, dzięki czemu integracja z systemami automatyki domowej tj. openHAB czy HomeAssistant jest bardzo prosta.

## Warunki wstępne
- urządzenia muszą być sprarowane i dodane do sieci - [AT_cmd_set.pdf](AT_cmd_set.pdf)
- należy znać identyfikatory urządzeń
- należy znać kody parametrów które mamy zamiar odczytywać i/lub te które mamy zamiar ustawiać - [codes](codes)

## Topic MQTT
Topic jest budowany według schematu
```
PREFIX/ID/CODE/POSTFIX
```
gdzie
- `PREFIX` - stały prefix ustawiany w pliku [config.ini](config.ini)
- `ID` - id urządzenia
- `CODE` - parametr urządzenia np. temperatura
- `POSTFIX` - typ tematu, określa czy jest to input do urządzenia lub output z urządzenia. Możliwe wartości:
	- `state` - stan wysyłany przez urządzenie
	- `command` - wartość wysyłana do urządzenia

### Odczyt wartości parametru - `state`
Odczytywanie wartości parametru, polega na zasubskrybowaniu na odpowiedni topic. Dla przykładu aby odczytać temperaturę z urządzenia o `ID = 2` należy zasubskrybować się na topic 
```
uart/2/32/state
```
W wiadomośći MQTT otrzymamy odczytaną wartość, np. `225` co oznacza temperaturę `22.5°C`

### Ustawianie wartości parametry - `command`
Należy wysłać wiadomość MQTT z nową wartością parametru na odpowiedni topic. Dla przykładu aby ustawić roletę w pozycji 50% otwarcia należy wysłać wartość `50` na topic
```
uart/1/106/command
```

## Instalacja i uruchomienie

### Konfiguracja
Konfiguracja odbywa się poprzez edycje pliku [config.ini](config.ini). Należy ustawić odpowiedni port pod który podłączona jest antena oraz wprowadzić ustawienia do komunkacji z brokerem MQTT

### Zależności
Skrypt napisany jest w Python 3, którego należy mieć zainstalowanego. Następnie należy zainstalować zależności
```
pip3 install -r requirements.txt
```

### Uruchomienie
Wystarczy wystartować skrypt
```
python3 uarttomqtt.py
```

#### Uruchomienie jako service działający w tle
```
cp uarttomqtt.service /lib/systemd/system/uarttomqtt.service
```
przy czym należy zwrócić uwagę na ścieżki w pliku [uarttomqtt.service](uarttomqtt.service). Domyślny working directory ustawiony jest na `/opt/uarttomqtt/` - zaleca się właśnie tam umieścić skrypt
```
sudo systemctl daemon-reload
sudo systemctl enable uarttomqtt.service
sudo systemctl start uarttomqtt.service
```
Aby sprawdzić status
```
sudo systemctl status uarttomqtt.service
```

## Integracje
### openHAB
```
Bridge mqtt:broker:broker [host="raspberrypi", secure=false] {
    Thing topic uart {
        Channels:
            Type number:temperature     "Temperature"       [
                stateTopic="uart/2/32/state"
            ]
            Type dimmer:rollershutter    "Rollershutter"    [
                stateTopic="uart/1/106/state",
                commandTopic="uart/1/106/command"
            ]
    }
}
```
