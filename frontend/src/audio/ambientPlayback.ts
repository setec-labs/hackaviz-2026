/** Start by default, retrying blocked autoplay on a gesture until playback succeeds. */
export function startAmbientPlayback(
  audio: EventTarget & Pick<HTMLMediaElement, "play" | "pause">,
  gestures: EventTarget,
  onBlocked: () => void,
  onError: () => void,
): () => void {
  let cancelled = false;
  let pending = false;
  let blocked = false;

  const removeGestures = () => {
    gestures.removeEventListener("pointerdown", retry);
    gestures.removeEventListener("keydown", retry);
  };
  const onPlaying = () => {
    blocked = false;
    removeGestures();
  };
  const play = () => {
    pending = true;
    void audio.play().then(() => {
      if (cancelled) return;
      onPlaying();
    }).catch((cause: unknown) => {
      if (cancelled) return;
      if (cause instanceof DOMException && cause.name === "NotAllowedError") {
        blocked = true;
        onBlocked();
        gestures.addEventListener("pointerdown", retry);
        gestures.addEventListener("keydown", retry);
      } else {
        blocked = false;
        removeGestures();
        onError();
      }
    }).finally(() => { pending = false; });
  };
  const retry = (event: Event) => {
    if (!blocked || pending) return;
    // Let the explicit audio button own its gesture, avoiding a play/pause race.
    if (event.target instanceof Element && event.target.closest("[data-sound-toggle]")) return;
    play();
  };

  audio.addEventListener("playing", onPlaying);
  play();
  return () => {
    cancelled = true;
    removeGestures();
    audio.removeEventListener("playing", onPlaying);
    audio.pause();
  };
}
