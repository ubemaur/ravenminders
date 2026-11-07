// Keeps the header clock, the timeline's "now" line, the greeting and the
// "Up next" countdown current (every 30 s, in the browser's local time), and
// scrolls the timeline to the current time (or to the server's suggested
// start, 8 AM, on other days) when the page opens or the card is expanded.
// Without this script, the page still shows the values from when it loaded.
(function () {
  "use strict";

  var clock = document.querySelector(".clock");
  var timeline = document.querySelector(".timeline");
  var scroller = document.querySelector(".timeline-scroll");
  var nowLine = document.querySelector(".now-line");
  var greetingPart = document.querySelector(".greeting-part");
  var countdown = document.querySelector(".countdown[data-start]");

  // Same rules as _greeting_part / _countdown in app.py.
  function partOfDay(hour) {
    return hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening";
  }

  function parseLocal(iso) {  // "2026-11-07T14:00" as local time
    var p = iso.split(/[-T:]/).map(Number);
    return new Date(p[0], p[1] - 1, p[2], p[3] || 0, p[4] || 0);
  }

  function sameDayCountdown(ms) {
    var minutes = Math.ceil(ms / 60000);
    if (minutes <= 0) return "now";
    if (minutes < 60) return "in " + minutes + " min";
    var hours = Math.floor(minutes / 60);
    var rest = minutes % 60;
    return "in " + hours + " h" + (rest ? " " + rest + " min" : "");
  }

  function isoDate(d) {
    var month = String(d.getMonth() + 1).padStart(2, "0");
    var day = String(d.getDate()).padStart(2, "0");
    return d.getFullYear() + "-" + month + "-" + day;
  }

  function minuteOfDay(d) {
    return d.getHours() * 60 + d.getMinutes();
  }

  function showsToday(now) {
    return timeline !== null && timeline.dataset.date === isoDate(now);
  }

  function update() {
    var now = new Date();
    if (clock) {
      clock.querySelector(".clock-time").textContent =
        now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
      clock.querySelector(".clock-date").textContent =
        now.toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
      clock.setAttribute("datetime", now.toISOString());
    }
    if (nowLine) {
      nowLine.hidden = !showsToday(now);  // also hides it once midnight passes
      nowLine.style.setProperty("--now", minuteOfDay(now));
    }
    if (greetingPart) {
      greetingPart.textContent = partOfDay(now.getHours());
    }
    // Only same-day timed events count down; other days keep the server's
    // text ("tomorrow at 3:00 PM"), which stays correct until midnight.
    if (countdown && !countdown.hasAttribute("data-all-day")) {
      var start = parseLocal(countdown.dataset.start);
      if (isoDate(start) === isoDate(now)) {
        countdown.textContent = sameDayCountdown(start - now);
      }
    }
  }

  function scrollToStart() {
    if (!scroller || !timeline) return;
    var style = getComputedStyle(timeline);
    var hourHeight = parseFloat(style.getPropertyValue("--hour-h")) || 48;
    var pad = parseFloat(style.getPropertyValue("--pad")) || 0;
    var now = new Date();
    if (showsToday(now)) {
      // current time about a third of the way down
      var y = pad + (minuteOfDay(now) / 60) * hourHeight;
      scroller.scrollTop = y - scroller.clientHeight / 3;
    } else {
      // suggested hour (8 AM) at the top, with its label visible
      var minute = Number(scroller.dataset.scrollMinute) || 0;
      scroller.scrollTop = (minute / 60) * hourHeight;
    }
  }

  update();
  scrollToStart();
  setInterval(update, 30 * 1000);

  // A collapsed timeline has no size, so scroll it when it's expanded.
  var timelineCard = scroller && scroller.closest("details");
  if (timelineCard) {
    timelineCard.addEventListener("toggle", function () {
      if (timelineCard.open) scrollToStart();
    });
  }
})();
