# RigBridge – AI-Assistenten-Regeln (Einstieg)

> **Wichtig für GitHub Copilot:** Vor jeder Änderung am Projekt müssen die folgenden
> Regel-Dateien berücksichtigt werden. Sie sind verbindlich und haben Vorrang vor
> allgemeinen Empfehlungen.

---

## Pflichtlektüre vor jeder Änderung

| Datei | Inhalt |
|---|---|
| [requirements.md](requirements.md) | **Funktionale Anforderungen** – was muss das System leisten? Umsetzungsstatus je Anforderung |
| [design-rules.md](design-rules.md) | Architektur, UI/Backend-Trennung, Fehlerbehandlung, Sicherheit, Plattformunterstützung |
| [structure-rules.md](structure-rules.md) | Ordnerstruktur, Dateibenennungskonventionen, Platzierungsregeln |
| [coding-rules.md](coding-rules.md) | Python/JS-Standards, Code-Stil, Tests, Commits, Docker |

---

## Projektübersicht

**RigBridge** ist eine Browser-Anwendung mit folgenden Hauptfunktionen:

1. **USB / CI-V-Steuerung:** Funkgeräte werden über USB mittels CI-V-Protokoll angesteuert.
2. **CAT-Schnittstelle:** Eine CAT-API wird für die Integration mit Wavelog bereitgestellt.
3. **Browser-UI:** Nur Konfiguration (USB-Einstellungen, CAT-Port, API-Key, ...) – keine direkte Gerätesteuerung im Frontend.
4. **Protokollbeschreibungen:** YAML-Dateien pro Gerät/Hersteller beschreiben Befehle und Datentypen.

---

## Tech-Stack

| Bereich | Technologie |
|---|---|
| Backend | Python 3.11+ |
| Frontend | HTML5, CSS3, JavaScript (ES2022+) |
| Protokolldefinitionen | YAML |
| Container | Docker / docker-compose |

| Umgebung | Plattform |
|---|---|
| Produktion | Linux (Docker) |
| Entwicklung | Windows (nativ) oder Linux |

---

## Kurzreferenz: Wichtigste Regeln

- Kein Hardware-Zugriff aus dem Frontend.
- Python Backend: PEP 8, Type Hints, Google-Style Docstrings, 4 Spaces.
- JavaScript Frontend: 2 Spaces, Semikolons, JSDoc für öffentliche Funktionen.
- YAML-Protokolldateien folgen dem Schema in `protocols/general/`.
- Neue Geräte → eigene YAML in `protocols/manufacturers/<hersteller>/`.
- Leere Ordner erhalten `.gitkeep`.
- Secrets nicht im Klartext speichern; verschlüsselte Speicherung ist zu bevorzugen und umzusetzen.
- Docker: Multi-Stage-Build, keine Secrets im Image, `.dockerignore` ist Pflicht.

---

## Zusammenarbeit mit AI-Assistenten

- Sicherheit hat Priorität: Bei Architektur, Implementierung und Review ist grundsätzlich auf Security-Best-Practices zu achten.
- Best-Practice-Ansatz: Lösungen sollen robust, wartbar und plattformkompatibel umgesetzt werden.
- Konstruktives Feedback ist ausdrücklich erwünscht: Verbesserungsvorschläge, Kritik, Anmerkungen und sinnvolle Rückfragen sollen aktiv eingebracht werden.
