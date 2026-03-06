"""
Abstract Base Class für Transport-Layer.

Definiert die Schnittstelle für alle Transport-Implementierungen
(USB, LAN, etc.) mit gemeinsamer Funktionalität.
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, List
import asyncio
import time
from dataclasses import dataclass

from ..config.logger import RigBridgeLogger
from .connection_state import ConnectionState, TransportStatus

logger = RigBridgeLogger.get_logger(__name__)


@dataclass
class FrameData:
    """
    Generische Datenkapsel für Transport-Frames.

    Kann für verschiedene Protokolle verwendet werden (CI-V, CAT, etc.)
    """
    raw_bytes: bytes
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def __repr__(self) -> str:
        hex_str = ' '.join(f'{b:02X}' for b in self.raw_bytes)
        return f"FrameData(bytes={len(self.raw_bytes)}, hex={hex_str})"


class BaseTransport(ABC):
    """
    Abstrakte Basisklasse für Transport-Implementierungen.

    Definiert gemeinsame Schnittstelle und Funktionalität für:
    - Verbindungsmanagement (connect, disconnect, reconnect)
    - Frame-Übertragung (send, receive)
    - Unsolicited Frame Handling (Callbacks)
    - Status-Management (ConnectionState)
    """

    def __init__(self, transport_type: str = "Transport"):
        """
        Initialisiert BaseTransport.

        Args:
            transport_type: Name des Transport-Typs (für Logging)
        """
        self.transport_type = transport_type
        self.state = ConnectionState(transport_type)
        self.last_error: Optional[str] = None

        # Unsolicited Frame Handling (Event-basiert)
        self._unsolicited_handlers: List[Callable[[FrameData], None]] = []
        self._listening_task: Optional[asyncio.Task] = None
        self._stop_listening = asyncio.Event()
        self._unsolicited_queue: asyncio.Queue = asyncio.Queue()
        self._background_reader_task: Optional[asyncio.Task] = None

    @abstractmethod
    def connect(self) -> bool:
        """
        Stellt Verbindung her.

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """
        Trennt die Verbindung.

        Sollte auch Background-Tasks stoppen.
        WICHTIG: Implementierungen sollten _stop_background_reader() aufrufen!
        """
        pass

    def reconnect(self) -> bool:
        """
        Erzwingt Reconnect durch Disconnect + Connect.

        Returns:
            True wenn erfolgreich verbunden, False bei Fehler
        """
        logger.info(f"{self.transport_type}: Erzwinge Reconnect...")
        self.disconnect()
        time.sleep(0.5)  # Kurze Pause für Ressourcen-Release
        return self.connect()

    @abstractmethod
    def send_frame(self, frame: FrameData) -> bool:
        """
        Sendet einen Frame über den Transport.

        Args:
            frame: Zu sendende Frame-Daten

        Returns:
            True wenn erfolgreich, False bei Fehler
        """
        pass

    @abstractmethod
    def read_response(self, timeout: Optional[float] = None) -> Optional[FrameData]:
        """
        Liest eine Antwort vom Transport.

        Args:
            timeout: Optional: Timeout in Sekunden

        Returns:
            FrameData mit Antwort oder None bei Fehler/Timeout
        """
        pass

    # ========================================================================
    # Background Reader (Hook-Methoden für Subklassen)
    # ========================================================================

    def _start_background_reader(self) -> None:
        """
        Hook-Methode: Startet kontinuierlichen Background-Reader.

        Diese Methode wird automatisch beim connect() aufgerufen,
        um kontinuierlich eingehende Daten zu überwachen.

        Transport-Implementierungen (z.B. USBConnection) sollten diese
        Methode überschreiben, um einen kontinuierlichen Reader zu starten,
        der eingehende Daten überwacht und _push_unsolicited_frame() aufruft.

        WICHTIG: Der Reader läuft unabhängig von Handler-Registrierungen!
        Er empfängt ALLE Daten und legt sie in die Queue. Die Handler werden
        nur bei tatsächlicher Registrierung aufgerufen.

        Beispiel-Implementierung:
            >>> def _start_background_reader(self):
            ...     if not self._background_reader_task:
            ...         self._background_reader_task = asyncio.create_task(
            ...             self._continuous_reader()
            ...         )

        Default: Keine Aktion (für Transports, die keinen Reader brauchen)
        """
        pass

    def _stop_background_reader(self) -> None:
        """
        Hook-Methode: Stoppt kontinuierlichen Background-Reader.

        Diese Methode wird beim disconnect() oder wenn keine Handler
        mehr registriert sind aufgerufen.

        Transport-Implementierungen sollten hier ihre Background-Tasks
        sauber beenden.

        Beispiel-Implementierung:
            >>> def _stop_background_reader(self):
            ...     if self._background_reader_task:
            ...         self._background_reader_task.cancel()
            ...         self._background_reader_task = None

        Default: Keine Aktion
        """
        pass

    # ========================================================================
    # Unsolicited Frame Handling
    # ========================================================================

    def register_unsolicited_handler(
        self,
        handler: Callable[[FrameData], None]
    ) -> None:
        """
        Registriert einen Handler für unerwartete Frames.

        Der Handler wird aufgerufen, wenn ein Frame empfangen wird,
        der nicht als Antwort auf einen gesendeten Befehl erwartet wurde.

        Startet automatisch die Background-Task beim ersten Handler.

        Args:
            handler: Callback-Funktion, die bei unsolicited frames aufgerufen wird

        Beispiel:
            >>> def log_unsolicited(frame: FrameData):
            ...     logger.info(f"Unsolicited: {frame}")
            >>>
            >>> connection.register_unsolicited_handler(log_unsolicited)
        """
        if handler not in self._unsolicited_handlers:
            self._unsolicited_handlers.append(handler)
            logger.debug(f"Handler registriert für unsolicited frames (total: {len(self._unsolicited_handlers)})")

        # Starte Queue-Listener beim ersten Handler
        # Background-Reader läuft bereits, wenn verbunden (gestartet in connect())
        if len(self._unsolicited_handlers) == 1 and self.state.is_connected():
            # Versuche Background-Reader zu starten, falls noch nicht gestartet
            # (kann passieren wenn connect() vor Event Loop aufgerufen wurde)
            self._start_background_reader()
            # Starte Queue-Listener (verteilt Events an Handler)
            self._start_listening_for_unsolicited_frames()

    def unregister_unsolicited_handler(
        self,
        handler: Callable[[FrameData], None]
    ) -> None:
        """
        Entfernt einen registrierten Handler.

        Stoppt Background-Task, wenn keine Handler mehr vorhanden sind.

        Args:
            handler: Zu entfernender Handler
        """
        if handler in self._unsolicited_handlers:
            self._unsolicited_handlers.remove(handler)
            logger.debug(f"Handler entfernt (verbleibend: {len(self._unsolicited_handlers)})")

        # Stoppe Queue-Listener, wenn keine Handler mehr da sind
        # Background-Reader läuft weiter (wird nur bei disconnect() gestoppt)
        if not self._unsolicited_handlers:
            if self._listening_task:
                self._stop_listening_for_unsolicited_frames()

    def _start_listening_for_unsolicited_frames(self) -> None:
        """
        Startet Background-Task für unsolicited frame monitoring.

        Wird automatisch aufgerufen beim ersten Handler-Registration.
        """
        if self._listening_task is not None:
            logger.warning("Background-Task für unsolicited frames läuft bereits")
            return

        try:
            # Erstelle neue Event für diesen Lausch-Zyklus
            self._stop_listening = asyncio.Event()

            # Starte Background-Task
            self._listening_task = asyncio.create_task(
                self._listen_for_unsolicited_frames()
            )
            logger.debug("Background-Task für unsolicited frames gestartet")
        except RuntimeError as e:
            logger.warning(f"Kann Background-Task nicht starten (kein Event Loop): {e}")

    def _stop_listening_for_unsolicited_frames(self) -> None:
        """
        Stoppt Background-Task für unsolicited frames.

        Wird automatisch beim disconnect() oder wenn keine Handler mehr da sind aufgerufen.
        """
        if self._listening_task is None:
            return

        # Signalisiere der Task anzuhalten
        try:
            self._stop_listening.set()
        except RuntimeError:
            pass

        # Cleanup
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                logger.debug("Stopp-Signal für Background-Task gesendet")
        except RuntimeError:
            pass

        self._listening_task = None
        logger.debug("Background-Task für unsolicited frames gestoppt")

    async def _listen_for_unsolicited_frames(self) -> None:
        """
        Background-Task-Coroutine für ereignisbasiertes Lauschen.

        Wartet auf Events aus der Queue (keine zeitgesteuerten Polls!).
        Sobald ein unsolicited Frame in die Queue gelegt wird,
        werden alle registrierten Handler aufgerufen.

        Diese Methode blockiert effizient auf Queue.get() und wartet
        auf echte Datenempfangs-Events statt regelmäßig zu pollen.
        """
        logger.info(f"{self.transport_type}: Starte ereignisbasiertes Lauschen auf unsolicited frames...")

        try:
            while not self._stop_listening.is_set():
                try:
                    # Warte auf Event: Sobald Daten empfangen werden, wird die Queue gefüllt
                    # Diese await-Operation blockiert effizient ohne CPU-Last
                    frame = await asyncio.wait_for(
                        self._unsolicited_queue.get(),
                        timeout=0.5  # Kurzer Timeout nur für graceful shutdown check
                    )

                    if frame and self._unsolicited_handlers:
                        logger.debug(f"[RX] Unsolicited frame erkannt (ereignisbasiert): {frame}")

                        # Rufe alle registrierten Handler auf
                        for handler in self._unsolicited_handlers:
                            try:
                                handler(frame)
                            except Exception as e:
                                logger.error(f"Fehler in unsolicited frame handler: {e}")

                except asyncio.TimeoutError:
                    # Kein Frame empfangen - das ist normal, nur für shutdown check
                    continue

                except Exception as e:
                    logger.error(f"Fehler beim Lauschen auf unsolicited frames: {e}")
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"{self.transport_type}: Background-Task wurde abgebrochen")
        finally:
            logger.info(f"{self.transport_type}: Beende ereignisbasiertes Lauschen auf unsolicited frames")

    def _push_unsolicited_frame(self, frame: FrameData) -> None:
        """
        Legt einen unsolicited Frame in die Event-Queue.

        Diese Methode wird von konkreten Transport-Implementierungen
        (z.B. USBConnection) aufgerufen, sobald unerwartet Daten
        empfangen werden.

        WICHTIG: Diese Methode ist NON-BLOCKING und trigger-basiert.
        Sie wird aufgerufen, sobald der Low-Level-Transport erkennt,
        dass Daten eingetroffen sind, die nicht zu einer erwarteten
        Antwort gehören.

        Args:
            frame: Empfangener unsolicited Frame

        Beispiel:
            >>> # In USBConnection, wenn unerwartet Daten empfangen werden:
            >>> frame = FrameData(received_bytes)
            >>> self._push_unsolicited_frame(frame)
        """
        try:
            # Non-blocking put in Queue
            self._unsolicited_queue.put_nowait(frame)
            logger.debug(f"Unsolicited frame in Queue gelegt: {frame}")
        except asyncio.QueueFull:
            logger.warning("Unsolicited frame queue ist voll, Frame wird verworfen")
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen von unsolicited frame zur Queue: {e}")

    # ========================================================================
    # Context Manager Support
    # ========================================================================

    def __enter__(self):
        """Context Manager support."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context Manager cleanup."""
        self.disconnect()

    def __repr__(self) -> str:
        """String-Repräsentation."""
        status = "verbunden" if self.state.is_connected() else "getrennt"
        return f"{self.__class__.__name__}({status})"
