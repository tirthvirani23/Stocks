// Shared player for the echo practice pages.
// Each page sets window.ECHO = { key, sources: [{playlist:"PL..."} | {video:"ID", label:"..."}] }.
// Playlists are read in the browser through the YouTube IFrame API, so new videos appear automatically.
(function () {
  var C = window.ECHO, $ = function (id) { return document.getElementById(id); };
  var ids = [], sections = [], cur = 0, player, done = {};
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(C.key + ":" + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(C.key + ":" + k, JSON.stringify(v)); } catch (e) {} }
  };
  done = store.get("done", {});
  $("autonext").checked = store.get("autonext", false);
  $("speed").value = String(store.get("speed", 1));

  function msg(t) { $("msg").textContent = t; $("msg").hidden = !t; }
  function wait(fn, ms) {
    return new Promise(function (res) {
      var t0 = Date.now();
      (function tick() { var v = fn(); if (v || Date.now() - t0 > ms) res(v); else setTimeout(tick, 300); })();
    });
  }

  async function loadIds() {
    for (var i = 0; i < C.sources.length; i++) {
      var s = C.sources[i];
      if (s.video) { sections.push({ start: ids.length, label: s.label || "Extra video" }); ids.push(s.video); continue; }
      var before = JSON.stringify(player.getPlaylist() || null);
      player.cuePlaylist({ listType: "playlist", list: s.playlist });
      var list = await wait(function () {
        var p = player.getPlaylist();
        return p && p.length && JSON.stringify(p) !== before ? p : null;
      }, 20000);
      if (!list) continue;
      sections.push({ start: ids.length, label: s.label || "Playlist", list: s.playlist });
      list.forEach(function (v) { ids.push(v); });
    }
  }

  function render() {
    var g = $("grid"); g.innerHTML = "";
    var n = 0;
    ids.forEach(function (v, i) {
      var sec = sections.filter(function (s) { return s.start === i; })[0];
      if (sec && sections.length > 1) {
        var l = document.createElement("div"); l.className = "section-label"; l.textContent = sec.label; g.appendChild(l);
      }
      var b = document.createElement("button");
      b.textContent = i + 1; b.title = "Video " + (i + 1);
      if (done[v]) { b.className = "done"; n++; }
      if (i === cur) b.className = "cur";
      b.onclick = function () { go(i); };
      g.appendChild(b);
    });
    $("progress").textContent = n + " / " + ids.length + " done";
    $("barfill").style.width = (ids.length ? 100 * n / ids.length : 0) + "%";
    $("count").textContent = "Video " + (cur + 1) + " of " + ids.length;
    $("prev").disabled = cur === 0; $("next").disabled = cur >= ids.length - 1;
    var d = !!done[ids[cur]];
    $("mark").textContent = d ? "✓ Done" : "Mark as done"; $("mark").className = d ? "on" : "";
    var c = g.querySelector(".cur"); if (c) c.scrollIntoView({ block: "nearest" });
  }

  function go(i, autoplay) {
    if (i < 0 || i >= ids.length) return;
    cur = i; store.set("cur", i);
    $("vtitle").textContent = "";
    if (autoplay) player.loadVideoById(ids[i]); else player.cueVideoById(ids[i]);
    render();
  }

  function setDone(v, on) { if (on) done[v] = 1; else delete done[v]; store.set("done", done); render(); }

  function onState(e) {
    var d = player.getVideoData && player.getVideoData();
    if (d && d.title && d.video_id === ids[cur]) $("vtitle").textContent = d.title;
    if (e.data === YT.PlayerState.PLAYING) player.setPlaybackRate(Number($("speed").value));
    if (e.data === YT.PlayerState.ENDED && ids.length) {
      setDone(ids[cur], true);
      if ($("autonext").checked && cur < ids.length - 1) go(cur + 1, true);
    }
  }

  window.onYouTubeIframeAPIReady = function () {
    var first = C.sources[0];
    player = new YT.Player("yt", {
      playerVars: { rel: 0, modestbranding: 1, playsinline: 1 },
      events: {
        onReady: async function () {
          msg("Loading videos…");
          await loadIds();
          if (!ids.length) {
            msg("Couldn't load the playlist. Check your internet connection and reload the page.");
            return;
          }
          msg("");
          player.addEventListener("onStateChange", onState);
          go(Math.min(store.get("cur", 0), ids.length - 1));
        }
      }
    });
  };

  $("prev").onclick = function () { go(cur - 1); };
  $("next").onclick = function () { go(cur + 1); };
  $("mark").onclick = function () { setDone(ids[cur], !done[ids[cur]]); };
  $("replay").onclick = function () { if (player) { player.seekTo(Math.max(0, player.getCurrentTime() - 5), true); player.playVideo(); } };
  $("speed").onchange = function () { var r = Number(this.value); store.set("speed", r); if (player) player.setPlaybackRate(r); };
  $("autonext").onchange = function () { store.set("autonext", this.checked); };
  $("reset").onclick = function () { done = {}; store.set("done", done); render(); };
  document.addEventListener("keydown", function (e) {
    if (e.target.matches("input,select,textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "ArrowRight" || e.key === "n") { go(cur + 1); }
    else if (e.key === "ArrowLeft" || e.key === "p") { go(cur - 1); }
    else if (e.key === "r") { $("replay").click(); }
  });

  var s = document.createElement("script"); s.src = "https://www.youtube.com/iframe_api"; document.head.appendChild(s);
})();
