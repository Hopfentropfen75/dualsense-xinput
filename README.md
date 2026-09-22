# DualSense → Xbox-Controller

Macht aus einem PS5-DualSense einen virtuellen Xbox-360-Pad, den Windows und
jedes XInput-Spiel als echten Controller sieht. USB und Bluetooth.

## Start

```
pythonw tray.py     # empfohlen: Tray-Icon mit Bruecke und Akkuanzeige
python bridge.py    # nur die Bruecke, mit Live-Ausgabe im Terminal
```

Beim Start wird eine Sekunde lang die Ruhelage gemessen — den Controller
dabei liegen lassen. Danach ist er als XInput-Gerät aktiv.

```
python bridge.py --seconds 60     # automatisch beenden
python bridge.py --deadzone 0.12  # groessere Deadzone bei starkem Drift
python bridge.py --quiet          # ohne Live-Anzeige
```

## Batterieanzeige

```
python battery.py          # Tray-Icon neben der Uhr
pythonw battery.py         # dasselbe ohne Konsolenfenster
python battery.py --once   # einmal im Terminal ausgeben
```

Laeuft unabhaengig von `bridge.py` - der Controller laesst sich parallel
oeffnen. Das Symbol faerbt sich gruen / gelb / rot und zeigt bei Ladung
einen Blitz; der Umriss passt sich heller und dunkler Taskleiste an.

## Stickdrift pruefen

```
python driftcheck.py
```

Trennt Versatz (Ruhelage neben der Mitte - kalibrierbar) von Zittern
(wanderndes Rauschen - nur per Deadzone abzudecken) und empfiehlt einen
Wert.

## Wichtigste Regel: nur EINE Verbindung

Der DualSense kann gleichzeitig per USB **und** Bluetooth verbunden sein.
Dann sieht Windows zwei Gamepads, und Spiele bekommen widerspruechliche
Eingaben - konkret beobachtet in Forza Horizon 6: Gas und Bremse
gleichzeitig, Lenkung nur sporadisch, Menuetasten werden angezeigt aber
nicht angenommen.

Richtig verbinden:

1. Controller vollstaendig ausschalten (PS-Taste ~10s halten)
2. **danach** das USB-Kabel einstecken

So laeuft er ueber Kabel, laedt dabei, und liefert mit 1000 Hz die
vierfache Reportrate von Bluetooth. Fuer Bluetooth-Betrieb umgekehrt: Kabel
abziehen, dann koppeln.

Das ist die haeufigste Fehlerquelle ueberhaupt - vor allem, weil das
Einstecken zum Laden waehrend einer laufenden Bluetooth-Verbindung ganz
harmlos aussieht.

## Aufbau

| Datei | Aufgabe |
|---|---|
| `dualsense.py` | HID-Reports lesen und dekodieren (USB `0x01`, BT `0x31`) |
| `mapping.py` | DualSense-Zustand → XInput-Zustand, Deadzones, Tastenbelegung |
| `output.py` | Rückkanal: Rumble, Lightbar, Player-LEDs (BT mit CRC32) |
| `bridge.py` | Setzt alles zusammen und treibt den virtuellen Pad |
| `xinput_ref.py` | XInput-Leser, zum Gegenprüfen gegen einen echten Pad |
| `battery.py` | Batterieanzeige als Tray-Icon |
| `driftcheck.py` | Stickdrift messen und Deadzone empfehlen |
| `tray.py` | Bruecke und Akkuanzeige in einem Prozess (empfohlener Start) |

## Tastenbelegung

Kreuz→A, Kreis→B, Viereck→X, Dreieck→Y, L1/R1→LB/RB, L3/R3→Stickklick,
Create→Back, Options→Start, PS→Guide. Das Touchpad ist unbelegt.

Umbelegen über `Config.button_map` in `mapping.py`.

## Stolpersteine, die hier schon gelöst sind

**Der Pad braucht einen Weckruf.** ViGEm übernimmt nur Reports, die sich vom
vorherigen unterscheiden. Der Default-Report ist bereits Null — liegt der
DualSense also ruhig, schickt man nur Nullen, und der Pad bleibt auf seinem
uninitialisierten Startzustand stehen (hier: `L(-3356,-1869)`). `_prime()`
stößt ihn einmal an. Ohne das wirkt alles tot, obwohl die Kette korrekt läuft.

**Y-Achse dreht sich um.** DualSense zählt nach unten, XInput nach oben.

**Bluetooth verschiebt alles um ein Byte** und verlangt beim Schreiben eine
CRC32 über ein vorangestelltes `0xA2`. Ohne gültige CRC verwirft der
Controller den Report kommentarlos — Rumble bleibt dann einfach stumm.

**Voller Report erst nach Anfrage.** Über BT sendet der DualSense nur einen
10-Byte-Minimalreport, bis einmal ein Feature-Report gelesen wurde
(`enable_full_bt()`). Erst danach gibt es Gyro, Touchpad und Batterie.

**Ruhelage wandert zwischen Sitzungen.** Innerhalb einer Sitzung steht sie
bombenfest, aber nach dem Spielen setzt sich der Stick anders. Deshalb wird
bei jedem Start neu kalibriert statt einmal gespeichert — und es gibt einen
Schutz gegen den Fall, dass beim Start versehentlich ein Stick gehalten wird
(sonst haette der Stick in die Gegenrichtung sofort Vollausschlag).

**vgamepad gibt den virtuellen Pad nur im Destruktor frei.** Der
Rumble-Callback haelt eine Referenz auf die Bruecke, die Bruecke eine auf
den Pad - ein Zyklus, den das Refcounting nicht aufloest. Ohne den Zyklus
explizit zu brechen (`close()` in `bridge.py`) bleibt bei jedem Neustart ein
Pad im System stehen, und das Spiel sieht wieder mehrere Controller.

**Deadzone radial, nicht pro Achse.** Achsenweise entsteht ein spürbarer
Sprung auf der Diagonalen; radial wird der Rest sauber nachskaliert.

## Abhängigkeiten

`hidapi`, `vgamepad` (bringt den ViGEmBus-Treiber mit), fuer die
Batterieanzeige zusaetzlich `pystray` und `pillow`.

## Was noch fehlt

- Adaptive Trigger und haptisches Feedback (DualSense-Spezialitäten, die
  XInput gar nicht kennt)
- Gyro → Stick-Mapping für Zielhilfe
- Das physische DualSense-HID verstecken, damit Spiele nicht beide Geräte
  sehen (dafür bräuchte es HidHide)

## Lizenz

MIT - siehe [LICENSE](LICENSE).
