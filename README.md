# DualSense → Xbox-Controller

Macht aus einem PS5-DualSense einen virtuellen Xbox-360-Pad, den Windows und
jedes XInput-Spiel als echten Controller sieht. USB und Bluetooth.

## Start

```
pythonw tray.py            # empfohlen: Bruecke im Tray plus Cockpit
pythonw tray.py --hidden   # dasselbe ohne Fenster, z. B. fuer Autostart
python bridge.py           # nur die Bruecke, mit Live-Ausgabe im Terminal
```

Eine Verknuepfung auf `tray.py` genuegt: Der erste Start bringt Bruecke
und Fenster, jeder weitere holt nur das Fenster nach vorn. Wird das
Fenster geschlossen, laeuft die Bruecke im Tray weiter.

Beim Start wird eine Sekunde lang die Ruhelage gemessen — den Controller
dabei liegen lassen. Danach ist er als XInput-Gerät aktiv.

```
python bridge.py --seconds 60     # automatisch beenden
python bridge.py --deadzone 0.12  # Deadzone fest vorgeben statt aus dem Profil
python bridge.py --quiet          # ohne Live-Anzeige
```

## Cockpit

Das Fenster, das beim Start aufgeht: Verbindung (Controller -> Bruecke ->
Xbox-Pad mit Reportrate), Live-Eingaben so wie das Spiel sie sieht,
Forza-Telemetrie mit Reifenschlupf pro Rad, Verlauf von Bremse, Gas und
ABS, dazu alle Profil-Einstellungen. Tasten stehen mit PlayStation-Namen
da, das Xbox-Gegenstueck in Klammern - `✕ (A)`, `L1 (LB)`.

Technisch ist es eine lokale Seite (`ui/cockpit.html`), die der
Tray-Prozess auf 127.0.0.1 ausliefert (`webui.py`) und die in einem
Edge-App-Fenster ohne Adressleiste laeuft. Die Live-Werte kommen direkt
aus der Bruecke; die API verlangt ein Zufallstoken, das nur im Link des
Fensters steht. Wird das Fenster geschlossen, laeuft die Bruecke weiter -
wieder oeffnen per Desktop-Symbol oder Doppelklick aufs Tray-Symbol.

### Logo

Das DS-Monogramm mit leuchtendem Unterstrich steht auf Desktop-Symbol,
Fenster und Tray. Im Tray ist der Unterstrich die Akkuanzeige: Laenge =
Ladestand, blau = verbunden, gruen = laedt, rot = unter 20 %,
durchgestrichen = nicht verbunden. `python logo.py` erzeugt
`dualsense.ico` neu. Schrift: Chakra Petch (SIL Open Font License,
`assets/OFL-ChakraPetch.txt`).

## Profile und Einstellungen

Alles, was sich pro Spiel unterscheiden soll, steckt in einem Profil:
Trigger-Widerstand, Stick-Deadzones, Trigger-Kurve und Rumble-Staerke.
Mitgeliefert sind **Standard**, **Forza** und **Shooter**; im
Cockpit lassen sich Profile anlegen, loeschen und per Regler
einstellen. Aenderungen wirken nach ein bis zwei Sekunden, ohne Neustart.

**Automatisch pro Spiel:** Jedes Profil hat eine Liste von Teilen des
Exe-Namens (Forza: `forzahorizon, forzamotorsport`). Laeuft ein passendes
Programm, schaltet die Bruecke von selbst um. Abschaltbar im Fenster und
im Tray-Menue unter "Profil".

| Einstellung | Wirkung |
|---|---|
| Trigger-Modus | Racing: L2 als Bremse mit Druckpunkt, R2 leicht gedaempft. Racing + Feedback: dazu ABS-Pulsieren und Durchdreh-Vibration. Shooter: Abzugs-Druckpunkt auf R2. |
| Bremse: Druckpunkt / Kraft | Ab welcher Zone (0-8) und wie stark (1-8) L2 dagegenhaelt |
| Gas: Widerstand | Grundwiderstand auf R2 (0 = keiner) |
| ABS: Staerke / Frequenz | Wie kraeftig und schnell L2 pulsiert, wenn Raeder blockieren |
| Durchdrehen | Wie kraeftig R2 vibriert, wenn die Hinterraeder durchdrehen |
| Deadzone innen | Gegen Stickdrift - siehe `driftcheck.py` |
| Aeussere Zone | Ab hier gilt der Stick als voll ausgelenkt. "Reichweite messen" bestimmt den Wert: beide Sticks ein paar Mal am Anschlag kreisen lassen. |
| Anti-Deadzone | Springt direkt hinter der Deadzone auf diesen Wert und gleicht so die Deadzone des Spiels aus. Nur nutzen, wenn die Lenkung um die Mitte traege wirkt. |
| L2 / R2 Leerweg und Kurve | Getrennt pro Trigger. Leerweg gegen Antippen; Kurve > 1 macht den Anfang feiner. Bremse meist ohne Leerweg, Gas mit etwas. |
| Vibration: Staerke | Verstaerkt oder daempft das Rumble des Spiels |
| Gyro | Controller-Drehung steuert den rechten Stick - aus, nur beim Zielen (L2 gehalten) oder immer. Empfindlichkeit, Mindestausschlag und Richtung einstellbar. |

XInput kennt keinen Trigger-Widerstand - Spiele koennen ihn ueber den
virtuellen Pad nicht steuern, deshalb setzt ihn die Bruecke selbst. Beim
Beenden nimmt sie ihn zurueck. Gespeichert wird alles in `settings.json`.

### ABS-Gefuehl mit Forza-Telemetrie

Richtig gut wird "Racing + Feedback" mit Forzas Telemetrie: Dann pulsiert
L2 genau dann, wenn beim Bremsen ein Rad blockiert, und R2 vibriert, wenn
die Hinterraeder durchdrehen - aus dem echten Reifenschlupf. Im Spiel:

> Einstellungen > HUD und Gameplay > **Data Out** = An,
> **Data Out IP** = `127.0.0.1`, **Data Out Port** = `5300`

Ob Daten ankommen, zeigt das Cockpit im Tab "Live" und "Profile". Ohne
Telemetrie schaetzt die Bruecke ABS aus kraeftigem Bremsen plus Rumble.

### Gyro-Zielen

Im Shooter-Profil steuert die Drehung des Controllers den rechten Stick,
solange L2 (Zielen) gehalten wird. Der Gyro wird beim Start zusammen mit
den Sticks kalibriert - den Controller dabei ruhig liegen lassen.

Die Reichweite laesst sich auch im Terminal messen:

```
python rangecheck.py
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
