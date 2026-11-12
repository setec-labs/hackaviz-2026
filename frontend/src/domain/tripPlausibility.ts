import { rgba, type Rgba } from "../theme/palette";

/**
 * Au-dela de cette duree, un trajet de nuit est juge peu plausible : la personne aurait
 * vraisemblablement pris un taxi ou un VTC. Choix de visualisation, pas une donnee mesuree.
 */
export const IMPLAUSIBLE_TRIP_SECONDS = 2 * 60 * 60;

export const IMPLAUSIBLE_TRIP_LABEL = "Trajet de plus de 2 h : peu plausible (un taxi aurait sans doute été pris)";

export function isImplausibleTrip(durationSeconds: number): boolean {
  return durationSeconds > IMPLAUSIBLE_TRIP_SECONDS;
}

/** Couleur neutre, hors du degrade de l'indice, pour les trajets peu plausibles. */
export function implausibleTripColor(alpha = 255): Rgba {
  return rgba("neutral", alpha);
}
