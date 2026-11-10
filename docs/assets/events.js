// Click events for Google Analytics, shared by every page: which download and buy buttons get used.
// Only the button's place and platform are sent, nothing about the visitor. gtag is not loaded on local previews.
document.addEventListener('click', function (e) {
  if (typeof gtag !== 'function') return;
  var a = e.target.closest && e.target.closest('a[href]');
  if (!a) return;
  var place = a.id || (a.closest('nav') ? 'nav' : a.closest('footer') ? 'footer' : 'page');
  if (/gumroad\.com/.test(a.href)) {
    gtag('event', 'buy_click', { placement: place });
  } else if (/\/releases|android\.html/.test(a.href)) {
    gtag('event', 'download_click', {
      platform: /releases\/tag\/android|android\.html/.test(a.href) ? 'android' : 'windows',
      placement: place
    });
  }
});
