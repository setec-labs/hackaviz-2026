import { rgba, type Rgba } from "../theme/palette";

/**
 * Above this duration a night journey is displayed as implausible: another mode
 * would likely be chosen. This threshold is a visualization choice, not measured data.
 */
export const IMPLAUSIBLE_TRIP_SECONDS = 2 * 60 * 60;

export const IMPLAUSIBLE_TRIP_LABEL = "Trajet de plus de 2 h : peu plausible (un taxi aurait sans doute été pris)";

/** Return whether a trip exceeds the visualization's duration threshold. */
export function isImplausibleTrip(durationSeconds: number): boolean {
  return durationSeconds > IMPLAUSIBLE_TRIP_SECONDS;
}

/** Return the neutral color used for implausible journeys. */
export function implausibleTripColor(alpha = 255): Rgba {
  return rgba("neutral", alpha);
}
