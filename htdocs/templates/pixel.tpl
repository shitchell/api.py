% rebase('article.tpl', title="Pixel Tracking GIF", header="Beacon Demo")
% import time
<p>This is a simple demonstration of the pixel tracking API</p>

<pre>
&lt;img src="https://api.shitchell.com/pixel.gif" />
</pre>

<p>Using this HTML, a 1x1 pixel invisible gif is inserted just below this line. You can't see it, but you can view the results of its tracking <a target="_blank" href="/pixel?limit=3">here</a></p>

<img src="https://api.shitchell.com/pixel.gif?{{ time.time() }}" />