# Anti-DevTools Protection

## Full Implementation (7 methods)

```javascript
(function(){
    // 1. Debugger timing trap
    (function loop(){
        var t = performance.now();
        debugger;
        if (performance.now() - t > 100) {
            document.body.innerHTML = '';
            window.location = 'https://google.com';
        }
        setTimeout(loop, 2000);
    })();

    // 2. Console detection via toString getter
    setInterval(function(){
        var el = new Image();
        var devtools = false;
        Object.defineProperty(el, 'id', {
            get: function(){ devtools = true; }
        });
        console.log(el);
        console.clear();
        if (devtools) document.body.innerHTML = '';
    }, 1000);

    // 3. Window size detection (docked DevTools shrinks viewport)
    setInterval(function(){
        if (window.outerWidth - window.innerWidth > 160 ||
            window.outerHeight - window.innerHeight > 160)
            document.body.innerHTML = '';
    }, 1000);

    // 4. Keyboard shortcut blocking
    document.addEventListener('keydown', function(e){
        if (e.keyCode === 123) { e.preventDefault(); return false; }
        if (e.ctrlKey && e.shiftKey && [73,74,85].indexOf(e.keyCode) !== -1) {
            e.preventDefault(); return false;
        }
    });

    // 5. Right-click disable
    document.addEventListener('contextmenu', function(e){ e.preventDefault(); });

    // 6. Console method overrides
    ['log','warn','error','info','debug','table','trace','dir'].forEach(function(m){
        console[m] = function(){};
    });

    // 7. Infinite debugger via constructor (resists regex removal)
    (function(){
        function check(){
            (function(){ return false; })
                ['constructor']('debugger')
                ['call']();
            check();
        }
        try { check(); } catch(e){}
    })();
})();
```

| Method | Catches | Bypass |
|--------|---------|--------|
| Debugger timing trap | DevTools open (Sources panel) | `--disable-javascript` then override |
| Console getter | DevTools console active | Hard to bypass cleanly |
| Window size | Docked DevTools (side/bottom) | Undocked DevTools window |
| Keyboard blocking | F12, Ctrl+Shift+I/J, Ctrl+U | Menu → More Tools → Developer Tools |
| Right-click | Inspect Element via context menu | Keyboard shortcut (if not blocked) |
| Console overrides | Console logging attempts | Restore from iframe |
| Infinite debugger (constructor) | Breakpoint stepping | Can't remove with simple regex |

## npm Alternative

`disable-devtool` library:

```html
<script src="https://cdn.jsdelivr.net/npm/disable-devtool"></script>
```

Detection modes: RegToString, DefineId, Size, DateToString, FuncToString, Debugger, Performance, DebugLib (Eruda/VConsole).

## Where to Apply

Apply to: landing pages with forms, tracking scripts, any page with sensitive JS logic.
Don't apply to: server-side code, proxied content, CSS/HTML.
