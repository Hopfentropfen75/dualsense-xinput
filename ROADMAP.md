# Roadmap

Was die Bruecke noch besser machen koennte, grob nach Nutzen fuer
Rennspiele (Forza Horizon) sortiert.

## Eingabe

- [ ] **Aeussere Deadzone / Stick-Reichweite kalibrieren** - viele Sticks
      erreichen 0/255 nicht ganz, besonders diagonal. Dann kommt nie voller
      Lenkeinschlag an. Maximalwerte beim Kreisen messen und darauf skalieren.
- [ ] **Anti-Deadzone** - die Bruecke zieht 8 % ab, das Spiel oft nochmal
      20-25 %. Direkt hinter der eigenen Zone auf die Spielschwelle springen,
      damit der Stick um die Mitte nicht traege wirkt.
- [ ] **Trigger-Deadzone und -Kurve** - L2/R2 gehen roh 1:1 durch. Kleine
      Zone gegen Antippen, optional progressive Kurve fuers Gas.
- [ ] **Stick-Kurven** - linear / progressiv fuer feines Lenken.
- [ ] **Einstellungen im Anzeigefenster** - Deadzones und Kurven per Regler
      statt per Kommandozeile, gespeichert in `settings.json`.

## Feedback

- [ ] **Trigger-Profile feinjustieren** - Druckpunkt und Staerke der Bremse
      per Regler, eigene Profile anlegen.
- [ ] **Rumble-Verstaerker** - Faktor fuer die Motorstaerke, falls die
      Emulation zu schwach wirkt.
- [ ] **Live-Trigger ausbauen** - Bremse bei starkem Rumble pulsieren lassen
      (ABS-Gefuehl), Frequenz aus dem leichten Motor ableiten.
- [ ] **Echte Haptik** - die Voice-Coil-Motoren laufen ueber einen
      Audiokanal (nur USB). Grosses Projekt.

## Komfort

- [ ] **Profil pro Spiel** - laufenden Prozess erkennen (z. B.
      `ForzaHorizon6.exe`) und automatisch auf "Racing" schalten.
- [ ] **Autostart mit Windows** - Schalter im Tray-Menue.
- [ ] **Physischen DualSense verstecken (HidHide)** - Spiele mit eigener
      DualSense-Unterstuetzung sehen sonst zwei Controller.
- [ ] **Gyro-Zielen** - Bewegungssensor auf den rechten Stick, nur solange
      eine Taste gehalten wird.
- [ ] **Touchpad belegen** - Klick auf Back/View oder als Maus.
- [ ] **Lightbar zeigt Akku** - Farbe wechselt bei niedrigem Stand.

## Technik

- [ ] **Latenz messen** - Vorher/Nachher der Warteschlangen-Leerung per USB
      belegen, Messskript nach `tools/`.
- [ ] **Schlanker Decode-Pfad** - fuer die Bruecke nur Sticks, Trigger und
      Tasten dekodieren.
- [ ] **Tests** - Mapping, Deadzones und Output-Report-Layout als Unit-Tests.

## Erledigt

- [x] Eingabe-Warteschlange leeren statt Rueckstau (USB 1000 Hz)
- [x] ViGEm nur bei Aenderung aktualisieren
- [x] Schutz gegen Doppelstart, Desktop-Verknuepfungen mit Icon
- [x] Anzeigefenster mit Status und Live-Eingaben
- [x] Adaptive Trigger mit Profilen (Racing, Racing + Rumble, Shooter)
- [x] Kraeftigere Rumble-Emulation ab Firmware 2.21
- [x] Lightbar- und Player-LED-Offsets nach hid-playstation korrigiert
