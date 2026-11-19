/* Weighted smooth scrolling for the inner pages. The homepage runs its own, tied to its scroll scenes. */
(function () {
  if (!window.Lenis || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  window.vsLenis = new Lenis({ lerp: 0.11, autoRaf: true, anchors: { offset: -24 } });
})();
