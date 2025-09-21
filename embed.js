// embed.js - coloque este arquivo no seu domínio (ex: https://meuservidor.com/embed.js)


function append(who, text){
const d = document.createElement('div');
d.style.margin = '6px 0';
d.style.padding = '8px 12px';
d.style.borderRadius = '12px';
d.style.maxWidth = '80%';
d.style.background = who === 'user' ? '#b30000' : '#222';
d.style.color = who === 'user' ? '#fff' : '#ddd';
d.style.marginLeft = who === 'user' ? 'auto' : '0';
d.textContent = text;
log.appendChild(d);
log.scrollTop = log.scrollHeight;
}


async function send(){
const m = input.value.trim();
if(!m) return; append('user', m); input.value = '';
append('bot', '...');
try{
const res = await fetch(apiBase + '/chat', {
method: 'POST',
headers: {'Content-Type':'application/json'},
body: JSON.stringify({ message: m, client_id: client, session_id: session_id })
});
const j = await res.json();
// remove last placeholder
if(log.lastChild) log.removeChild(log.lastChild);
if(j.error) append('bot', 'Erro: ' + j.error); else append('bot', j.response || '');
}catch(e){
if(log.lastChild) log.removeChild(log.lastChild);
append('bot', 'Erro de conexão');
}
}


btn.addEventListener('click', send);
input.addEventListener('keydown', e => { if(e.key === 'Enter') send(); });
});
}


// load on DOM ready
if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load); else load();
})();
