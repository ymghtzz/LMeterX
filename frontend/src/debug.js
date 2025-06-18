// Resource loading check script
// Add this script to index.html to help diagnose static resource loading issues

(function () {
  // Output page environment information
  console.log('Page URL:', window.location.href);
  console.log('User Agent:', navigator.userAgent);

  // Function to try loading a resource
  async function checkResource(url) {
    try {
      const response = await fetch(url, { method: 'HEAD' });
      console.log(
        `Resource ${url} status:`,
        response.status,
        response.ok ? 'Success' : 'Failure'
      );
      if (response.ok) {
        const contentType = response.headers.get('content-type');
        console.log(`Resource ${url} content type:`, contentType);
      }
      return response.ok;
    } catch (error) {
      console.error(`Resource ${url} loading error:`, error.message);
      return false;
    }
  }

  // Check resources after the page has loaded
  window.addEventListener('load', async () => {
    console.log('Page loaded, starting resource check...');

    // Check CSS files
    const cssLinks = Array.from(
      document.querySelectorAll('link[rel="stylesheet"]')
    );
    console.log('Detected CSS files:', cssLinks.length);
    for (const link of cssLinks) {
      const href = link.getAttribute('href');
      console.log(`Checking CSS: ${href}`);
      await checkResource(href);
    }

    // Check JS files
    const scripts = Array.from(document.querySelectorAll('script[src]'));
    console.log('Detected JS files:', scripts.length);
    for (const script of scripts) {
      const src = script.getAttribute('src');
      console.log(`Checking JS: ${src}`);
      await checkResource(src);
    }

    // Check common static resource paths
    const commonPaths = ['/assets/', '/assets/index.css', '/assets/index.js'];

    console.log('Checking common static resource paths...');
    for (const path of commonPaths) {
      await checkResource(path);
    }

    console.log('Resource check complete');
  });
})();
