import { useEffect, useRef, useState } from "react";
import ambientLoopUrl from "../assets/ambient-loop.wav?url";
import type { ArrivalChime } from "../audio/arrivalChime";

export function SoundOptions({ chime }: { chime?: ArrivalChime }) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isStarting, setIsStarting] = useState(false);
  const [volume, setVolume] = useState(50);
  const [autoplayBlocked, setAutoplayBlocked] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chimeEnabled, setChimeEnabled] = useState(chime?.enabled ?? false);

  useEffect(() => {
    const audio = audioRef.current;
    if (audio) audio.volume = volume / 100;
    if (chime) chime.volume = volume / 100;
  }, [volume, chime]);

  useEffect(() => {
    if (chime) chime.enabled = chimeEnabled;
  }, [chimeEnabled, chime]);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    let cancelled = false;
    void audio.play().catch((cause: unknown) => {
      if (cancelled) return;
      if (cause instanceof DOMException && cause.name === "NotAllowedError") {
        setAutoplayBlocked(true);
      } else {
        setError("Impossible de lire l'ambiance sonore. Réessayez.");
      }
    });
    return () => {
      cancelled = true;
      audio.pause();
    };
  }, []);

  const toggleSound = async () => {
    const audio = audioRef.current;
    if (!audio) return;
    if (!audio.paused) {
      audio.pause();
      return;
    }

    setError(null);
    setIsStarting(true);
    try {
      if (audio.error) audio.load();
      await audio.play();
    } catch {
      setError("Impossible de lire l'ambiance sonore. Vérifiez la sortie audio puis réessayez.");
    } finally {
      setIsStarting(false);
    }
  };

  return (
    <details className="mt-2 border-t border-surface-raised pt-2 text-xs">
      <summary className="w-fit cursor-pointer rounded text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-selection">
        Options{autoplayBlocked ? " · Son en attente" : ""}
      </summary>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
        <audio
          ref={audioRef}
          src={ambientLoopUrl}
          loop
          preload="auto"
          onPlaying={() => {
            setIsPlaying(true);
            setAutoplayBlocked(false);
            setError(null);
          }}
          onPause={() => setIsPlaying(false)}
          onError={() => {
            setIsPlaying(false);
            setError("Le fichier d'ambiance sonore est indisponible ou illisible. Réessayez.");
          }}
        />
        <button
          type="button"
          aria-pressed={isPlaying}
          disabled={isStarting}
          onClick={() => void toggleSound()}
          className="rounded-full border border-surface-raised px-3 py-1 text-ink hover:border-selection focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-selection disabled:opacity-50"
        >
          {isStarting ? "Chargement du son…" : isPlaying ? "Désactiver l'ambiance sonore" : "Activer l'ambiance sonore"}
        </button>
        <label htmlFor="ambient-volume" className="text-ink-muted">
          Volume
        </label>
        <input
          id="ambient-volume"
          type="range"
          min={0}
          max={100}
          step={1}
          value={volume}
          onChange={(event) => setVolume(Number(event.target.value))}
          aria-valuetext={`${volume} %`}
          className="w-24 cursor-pointer accent-selection focus-visible:outline-2 focus-visible:outline-selection"
        />
        <span className="w-9 font-mono text-ink-muted tabular-nums" aria-hidden="true">{volume} %</span>
        <p className="w-full text-ink-muted">Boucle de 41 secondes, indépendante de la simulation.</p>
        {chime && (
          <label className="flex w-full cursor-pointer items-center gap-2 text-ink">
            <input
              type="checkbox"
              checked={chimeEnabled}
              onChange={(event) => setChimeEnabled(event.target.checked)}
              className="cursor-pointer accent-selection focus-visible:outline-2 focus-visible:outline-selection"
            />
            Tintement à chaque arrivée (même volume)
          </label>
        )}
        {autoplayBlocked && (
          <p role="status" className="w-full text-ink-muted">
            Le navigateur bloque la lecture automatique. Cliquez sur « Activer l'ambiance sonore ».
          </p>
        )}
        {error && <p role="alert" className="w-full text-vigilance">{error}</p>}
      </div>
    </details>
  );
}
