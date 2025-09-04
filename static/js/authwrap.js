// Auto-add Authorization for all /me/* and /tengine/* calls (fetch + XHR), same-origin only.
(function(){
  const getToken = () => localStorage.getItem('token') || '';

  function isApi(urlStr){
    try{
      const u = new URL(urlStr, window.location.href);
      return (u.origin === window.location.origin) &&
             (u.pathname.startsWith('/me/') || u.pathname.startsWith('/tengine/'));
    }catch(e){ return false; }
  }

  // ---- fetch ----
  const origFetch = window.fetch;
  window.fetch = function(input, init){
    const urlStr = (typeof input === 'string') ? input : (input && input.url) || '';
    if (isApi(urlStr)) {
      init = init || {};
      const headers = new Headers((init && init.headers) || (typeof input !== 'string' && input.headers) || {});
      headers.set('Authorization', 'Bearer ' + getToken());
      init.headers = headers;
      if (typeof input !== 'string') {
        input = new Request(urlStr, { ...input, headers });
      }
    }
    return origFetch(input, init);
  };

  // ---- XHR (axios, raw XMLHttpRequest) ----
  const origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url, async, user, password){
    this.__ap_url = url;
    return origOpen.call(this, method, url, async !== false, user, password);
  };
  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function(body){
    try{
      if (this.__ap_url && isApi(this.__ap_url)) {
        this.setRequestHeader('Authorization', 'Bearer ' + getToken());
      }
    }catch(_){}
    return origSend.call(this, body);
  };
})();
