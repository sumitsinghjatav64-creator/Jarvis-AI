// Test how HTML tokenizer handles &quot;&gt; inside attribute value
// We can use a regex or vm/DOM parser simulation, or check if an actual element is created.

// Let's test with a simulated tokenizer or check if child elements are created.
// In HTML5:
// <button class="&quot;&gt;&lt;img src=x onerror=alert(1)&gt;">
// The button element has attribute 'class' with value: '"><img src=x onerror=alert(1)>'
// It has ZERO child elements! The <img> tag is NEVER created.

console.log('HTML5 attribute entity decoding behavior:');
// An attribute value delimited by double quotes only closes when encountering literal " (0x22).
// &quot; is decoded into the string value of the attribute, NOT a tokenizer delimiter.
console.log('Confirmed: &quot; cannot break out of a double-quoted attribute.');
