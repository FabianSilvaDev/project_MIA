function serve() {
    const http = require('http');
    const server = http.createServer((req, res) => {
        res.writeHead(200, {'Content-Type': 'text/html'});
        res.end('<h1>Hello from Node.js!</h1>');
    });
    server.listen(3344, () => {
        console.log('Server running on port 3344.');
    });
}