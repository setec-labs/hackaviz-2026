import type { GeoPointDto, SafetyIndexResponseDto } from "../api/contracts";
import { createRandom, randomBetween } from "./random";

/*
 * Champ SIMULE d'indice lie au sentiment de securite.
 * Les zones sont tirees aleatoirement et n'ont AUCUN lien avec des lieux reels :
 * ces valeurs servent uniquement a tester la visualisation.
 */

interface Blob {
  longitude: number;
  latitude: number;
  /** Rayon en degres. */
  radius: number;
  /** Contribution a l'indice (negative = moins favorable). */
  amplitude: number;
}

export interface MockSafetyField {
  valueAt(point: GeoPointDto): number | null;
}

export function createMockSafetyField(seed: number): MockSafetyField {
  const random = createRandom(seed ^ 0x5afe7);
  // Zones tirees dans le coeur de l'agglomeration, la ou passent la majorite des trajets simules.
  const randomBlob = (radius: [number, number], amplitude: [number, number]): Blob => ({
    longitude: randomBetween(random, 2.0, 2.75),
    latitude: randomBetween(random, 48.65, 49.05),
    radius: randomBetween(random, ...radius),
    amplitude: randomBetween(random, ...amplitude),
  });

  const blobs: Blob[] = [
    ...Array.from({ length: 45 }, () => randomBlob([0.008, 0.03], [-0.65, -0.3])),
    ...Array.from({ length: 12 }, () => randomBlob([0.01, 0.04], [0.08, 0.18])),
  ];
  // Petites zones sans donnees pour exercer l'etat "indicateur non disponible".
  const missingAreas: Blob[] = Array.from({ length: 10 }, () => randomBlob([0.008, 0.02], [0, 0]));

  return {
    valueAt({ latitude, longitude }) {
      for (const area of missingAreas) {
        if (Math.hypot(longitude - area.longitude, latitude - area.latitude) < area.radius) {
          return null;
        }
      }
      let value = 0.72 + 0.08 * Math.sin(longitude * 47) * Math.cos(latitude * 53);
      for (const blob of blobs) {
        const d2 = (longitude - blob.longitude) ** 2 + (latitude - blob.latitude) ** 2;
        value += blob.amplitude * Math.exp(-d2 / (2 * blob.radius * blob.radius));
      }
      return Math.round(Math.min(1, Math.max(0, value)) * 1000) / 1000;
    },
  };
}

/** Produit une reponse au format de l'API indice, dans l'ordre des points demandes. */
export function generateMockSafetyResponse(field: MockSafetyField, points: GeoPointDto[]): SafetyIndexResponseDto {
  return {
    indices: points.map((point) => ({ ...point, value: field.valueAt(point) })),
  };
}
