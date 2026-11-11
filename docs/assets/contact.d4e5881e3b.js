/* Small enhancement only; phone, map and email links work without JavaScript. */
(function(){
  var button=document.getElementById('copy-contact-email');
  var address=document.getElementById('contact-email-address');
  var status=document.getElementById('contact-copy-status');
  if(!button||!address||!status) return;
  button.addEventListener('click',async function(){
    try{
      if(!navigator.clipboard) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(address.textContent.trim());
      status.textContent='Η διεύθυνση email αντιγράφηκε.';
    }catch(e){
      status.textContent='Μπορείτε να επιλέξετε και να αντιγράψετε τη διεύθυνση info@synoida.gr.';
    }
  });
})();
