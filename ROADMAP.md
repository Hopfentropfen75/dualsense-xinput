# Roadmap

Was die Bruecke noch besser machen koennte, grob nach Nutzen fuer
Rennspiele (Forza Horizon) sortiert.

## Eingabe

- [x] **Aeussere Deadzone / Stick-Reichweite kalibrieren** - viele Sticks
      erreichen 0/255 nicht ganz, besonders diagonal. Dann kommt nie voller
      Lenkeinschlag an. Maximalwerte beim Kreisen messen und darauf skalieren.
- [x] **Anti-Deadzone** - die Bruecke zieht 8 % ab, das Spiel oft nochmal
      20-25 %. Direkt hinter der eigenen Zone auf die Spielschwelle springen,
      damit der Stick um die Mitte nicht traege wirkt.
- [x] **Trigger-Deadzone und -Kurve** - L2/R2 gehen roh 1:1 durch. Kleine
      Zone gegen Antippen, optional progressive Kurve fuers Gas.
- [ ] **Stick-Kurven** - linear / progressiv fuer feines Lenken.
- [x] **Einstellungen im Anzeigefenster** - Deadzones und Kurven per Regler
      statt per Kommandozeile, gespeichert in `settings.json`.

## Feedback

- [x] **Trigger-Profile feinjustieren** - Druckpunkt und Staerke der Bremse
      per Regler, eigene Profile anlegen.
- [x] **Rumble-Verstaerker** - Faktor fuer die Motorstaerke, falls die
      Emulation zu schwach wirkt.
- [x] **Live-Trigger ausbauen** - Bremse bei starkem Rumble pulsieren lassen
      (ABS-Gefuehl), Frequenz aus dem leichten Motor ableiten.
- [ ] **Echte Haptik** - die Voice-Coil-Motoren laufen ueber einen
      Audiokanal (nur USB). Grosses Projekt.

## Komfort

- [x] **Profil pro Spiel** - laufenden Prozess erkennen (z. B.
      `ForzaHorizon6.exe`) und automatisch auf "Racing" schalten.
- [ ] **Autostart mit Windows** - Schalter im Tray-Menue.
- [ ] **Physischen DualSense verstecken (HidHide)** - Spiele mit eigener
      DualSense-Unterstuetzung sehen sonst zwei Controller.
- [x] **Gyro-Zielen** - Bewegungssensor auf den rechten Stick, nur solange
      eine Taste gehalten wird.
- [ ] **Touchpad belegen** - Klick auf Back/View oder als Maus.
- [ ] **Lightbar zeigt Akku** - Farbe wechselt bei niedrigem Stand.

## Ideen aus dem Feedback

- [ ] **Telemetrie weiter nutzen** - Lightbar als Drehzahlanzeige, Rumble
      bei Rumpelstreifen (Forza liefert beides).
- [ ] **Gyro-Glaettung** - leichtes Filtern gegen Zittern bei hoher
      Empfindlichkeit.

## Technik

- [ ] **Latenz messen** - Vorher/Nachher der Warteschlangen-Leerung per USB
      belegen, Messskript nach `tools/`.
- [ ] **Schlanker Decode-Pfad** - fuer die Bruecke nur Sticks, Trigger und
      Tasten dekodieren.
- [x] **Tests** - Mapping, Deadzones und Output-Report-Layout als Unit-Tests.

## Erledigt

- [x] Thread-Wechsel auf 0,5 ms, damit Cockpit und Co. die Eingabe nicht bremsen
- [x] Doppelstart-Sperre mit verlaesslichem Fehlercode
- [x] Logdatei statt stummer Fehler
- [x] Sperre beim Speichern der Einstellungen
- [x] Schriften lokal statt von Google
- [x] requirements.txt und GitHub-Check

- [x] Eingabe-Warteschlange leeren statt Rueckstau (USB 1000 Hz)
- [x] ViGEm nur bei Aenderung aktualisieren
- [x] Schutz gegen Doppelstart, Desktop-Verknuepfungen mit Icon
- [x] Cockpit (Edge-App-Fenster) mit Live-Eingaben, Telemetrie, Verlauf und Profilen
- [x] Adaptive Trigger mit Profilen (Racing, Racing + Rumble, Shooter)
- [x] Kraeftigere Rumble-Emulation ab Firmware 2.21
- [x] Lightbar- und Player-LED-Offsets nach hid-playstation korrigiert
