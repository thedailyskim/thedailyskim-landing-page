/* A link visit never records a vote. Only the confirmation button sends a POST. */
(function () {
  'use strict';
  var endpoint = 'https://energized-kiwi-650.convex.site/v1/votes';
  var key = 'thedailyskim.poll-voter.v1';
  var lifetime = 30 * 24 * 60 * 60 * 1000;
  var heading = document.getElementById('poll-heading');
  var status = document.getElementById('poll-status');
  var selected = document.getElementById('vote');
  var button = document.getElementById('confirm-vote');
  var query = new URLSearchParams(location.search);
  var poll = query.get('poll') || '';
  var vote = query.get('vote') || '';
  var pending = false;
  var complete = false;
  var identityUnavailable = false;
  function label(choice) { return choice === 'yes' ? 'Yes' : 'No'; }
  function voter() {
    // Do not silently fall back to a new identity if storage is blocked/corrupt.
    if (!window.crypto || !window.crypto.getRandomValues) throw new Error('identity');
    var now = Date.now();
    var stored = window.localStorage.getItem(key);
    var record;
    if (stored !== null) {
      record = JSON.parse(stored);
      if (!record || !/^[a-f0-9]{32}$/.test(record.id) ||
          !Number.isFinite(record.expires) || record.expires > now + lifetime ||
          record.expires <= 0) throw new Error('identity');
      if (record.expires > now) return record.id;
    }
    var bytes = new Uint8Array(16);
    window.crypto.getRandomValues(bytes);
    var id = Array.from(bytes, function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    record = JSON.stringify({ id: id, expires: now + lifetime });
    window.localStorage.setItem(key, record);
    if (window.localStorage.getItem(key) !== record) throw new Error('identity');
    return id;
  }
  if (query.getAll('poll').length !== 1 || query.getAll('vote').length !== 1 ||
      !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(poll) || poll.length > 100 ||
      (vote !== 'yes' && vote !== 'no')) {
    heading.textContent = 'Check your poll link';
    status.textContent = 'No vote was sent. Open the Yes or No link in the edition, then confirm your choice here.';
    return;
  }
  selected.textContent = 'Selected: ' + label(vote);
  selected.hidden = false;
  button.textContent = 'Confirm ' + label(vote);
  button.hidden = false;
  button.addEventListener('click', async function () {
    if (pending || complete || identityUnavailable) return;
    pending = true;
    button.disabled = true;
    var id;
    try {
      id = voter();
    } catch (_) {
      identityUnavailable = true;
      heading.textContent = 'Your vote was not sent';
      status.textContent = 'Secure browser storage is unavailable. Allow local storage and use a secure browser, then reload this page. We do not create a replacement identity when storage fails.';
      button.textContent = 'Browser storage unavailable';
      pending = false;
      return;
    }
    status.textContent = 'Sending your confirmation…';
    var controller = new AbortController();
    var timeout = setTimeout(function () { controller.abort(); }, 15000);
    try {
      var response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'omit',
        referrerPolicy: 'no-referrer',
        body: JSON.stringify({ brand: 'thedailyskim', poll: poll, vote: vote, voter: id }),
        signal: controller.signal
      });
      var result = await response.json();
      if (!response.ok && result && result.ok === false) {
        var errors = {
          poll_closed: ['This poll is closed', 'No vote was saved. This poll is no longer accepting answers.', 'Poll closed', true],
          unknown_poll: ['This poll is not available', 'No vote was saved. This poll is not registered with the voting service.', 'Poll unavailable', true],
          voting_disabled: ['Voting is temporarily unavailable', 'No vote was saved. Voting is temporarily unavailable. Please try again later.', 'Retry confirmation', false],
          poll_capacity_reached: ['Voting is temporarily unavailable', 'No vote was saved. This poll has reached its current capacity. Please try again later.', 'Retry confirmation', false]
        };
        var error = Object.prototype.hasOwnProperty.call(errors, result.error) ? errors[result.error] : null;
        if (error) {
          heading.textContent = error[0];
          status.textContent = error[1];
          button.textContent = error[2];
          complete = error[3];
          button.disabled = complete;
          return;
        }
      }
      if (!response.ok || !result || result.ok !== true ||
          typeof result.duplicate !== 'boolean' ||
          (result.vote !== 'yes' && result.vote !== 'no') ||
          (!result.duplicate && result.vote !== vote)) throw new Error('unconfirmed');
      complete = true;
      selected.textContent = 'Recorded: ' + label(result.vote);
      heading.textContent = result.duplicate ? 'You already answered this poll' : 'Thanks for confirming your vote';
      status.textContent = result.duplicate
        ? 'Your previously recorded answer is ' + label(result.vote) + '. It has not been changed.'
        : 'Your answer was recorded for this poll. Repeat confirmations from this browser do not add another vote.';
      button.textContent = 'Confirmed';
    } catch (_) {
      heading.textContent = 'Your vote could not be confirmed';
      status.textContent = 'We could not confirm a response from the poll service. Retry with this browser. If the first request arrived, retrying will not count it twice.';
      button.textContent = 'Retry confirmation';
      button.disabled = false;
    } finally {
      clearTimeout(timeout);
      pending = false;
    }
  });
})();
