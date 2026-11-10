const timeFormatter = new Intl.DateTimeFormat("fr-FR", {
  timeZone: "Europe/Paris",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  timeZone: "Europe/Paris",
  weekday: "short",
  day: "numeric",
  month: "short",
});

/** Heure de Paris correspondant a un temps simule relatif a `originMs`. */
export function formatSimulatedTime(originMs: number, simulatedSeconds: number): string {
  return timeFormatter.format(new Date(originMs + simulatedSeconds * 1000));
}

export function formatSimulatedDate(originMs: number, simulatedSeconds: number): string {
  return dateFormatter.format(new Date(originMs + simulatedSeconds * 1000));
}

export function formatDuration(seconds: number): string {
  const totalMinutes = Math.round(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return hours > 0 ? `${hours} h ${String(minutes).padStart(2, "0")}` : `${minutes} min`;
}

export function formatIndex(value: number | null): string {
  return value === null || Number.isNaN(value) ? "non disponible" : value.toFixed(2).replace(".", ",");
}

const MODE_LABELS: Record<string, string> = {
  walk: "Marche",
  bike: "Vélo",
  night_bus: "Bus de nuit",
  car: "Voiture",
};

export function formatMode(mode: string | null): string {
  if (mode === null) {
    return "Mode non renseigné";
  }
  return MODE_LABELS[mode] ?? mode;
}
