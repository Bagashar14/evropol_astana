import os
import json
import re
from http.server import SimpleHTTPRequestHandler, HTTPServer
import sys

PORT = 8000
PRODUCTS_FILE = "products.json"
UPLOAD_DIR = "uploads"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

class EuropolRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Disable caching for API development
        if self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def do_GET(self):
        if self.path == '/api/products':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if os.path.exists(PRODUCTS_FILE):
                with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                    self.wfile.write(f.read().encode('utf-8'))
            else:
                self.wfile.write(b'[]')
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == '/api/products':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                new_product = json.loads(post_data)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            products = []
            if os.path.exists(PRODUCTS_FILE):
                with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                    try:
                        products = json.load(f)
                    except json.JSONDecodeError:
                        pass
            
            # Generate sequential ID
            if products:
                max_id = max(int(p['id']) for p in products if str(p['id']).isdigit())
                new_product['id'] = str(max_id + 1)
            else:
                new_product['id'] = "1"

            products.append(new_product)

            with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)

            self.send_response(201)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(new_product, ensure_ascii=False).encode('utf-8'))

        elif self.path == '/api/upload':
            # Handle multipart/form-data upload
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_error(400, "Content-Type must be multipart/form-data")
                return
            
            boundary_match = re.search(r'boundary=([^;]+)', content_type)
            if not boundary_match:
                self.send_error(400, "Boundary not found")
                return
            boundary = b'--' + boundary_match.group(1).encode()

            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)

            parts = body.split(boundary)
            for part in parts:
                if b'Content-Disposition' in part and b'filename="' in part:
                    # Separate headers and content
                    try:
                        headers_part, content_part = part.split(b'\r\n\r\n', 1)
                    except ValueError:
                        continue
                    
                    # Remove trailing CRLF and boundary artifacts
                    if content_part.endswith(b'\r\n'):
                        content_part = content_part[:-2]
                    elif content_part.endswith(b'\r\n--'):
                        content_part = content_part[:-4]
                    
                    headers_str = headers_part.decode('utf-8', errors='ignore')
                    filename_match = re.search(r'filename="([^"]+)"', headers_str)
                    if filename_match:
                        filename = filename_match.group(1)
                        filename = os.path.basename(filename) # Clean name
                        # Avoid duplicates
                        name, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(os.path.join(UPLOAD_DIR, filename)):
                            filename = f"{name}_{counter}{ext}"
                            counter += 1

                        filepath = os.path.join(UPLOAD_DIR, filename)
                        with open(filepath, 'wb') as f:
                            f.write(content_part)
                        
                        # Return uploaded image URL
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({"url": f"/uploads/{filename}"}).encode('utf-8'))
                        return
            
            self.send_error(400, "No file uploaded")
        else:
            self.send_error(404, "Not Found")

    def do_PUT(self):
        match = re.match(r'^/api/products/([^/]+)$', self.path)
        if match:
            product_id = match.group(1)
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                updated_fields = json.loads(post_data)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return

            products = []
            if os.path.exists(PRODUCTS_FILE):
                with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                    try:
                        products = json.load(f)
                    except json.JSONDecodeError:
                        pass
            
            updated_product = None
            for p in products:
                if str(p['id']) == str(product_id):
                    p.update(updated_fields)
                    p['id'] = str(product_id) # Preserve ID
                    updated_product = p
                    break
            
            if updated_product is None:
                self.send_error(404, "Product not found")
                return

            with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(updated_product, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")

    def do_DELETE(self):
        match = re.match(r'^/api/products/([^/]+)$', self.path)
        if match:
            product_id = match.group(1)
            products = []
            if os.path.exists(PRODUCTS_FILE):
                with open(PRODUCTS_FILE, 'r', encoding='utf-8') as f:
                    try:
                        products = json.load(f)
                    except json.JSONDecodeError:
                        pass
            
            initial_len = len(products)
            products = [p for p in products if str(p['id']) != str(product_id)]
            
            if len(products) == initial_len:
                self.send_error(404, "Product not found")
                return

            with open(PRODUCTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")

def run(server_class=HTTPServer, handler_class=EuropolRequestHandler, port=PORT):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Starting Europol local server on port {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        sys.exit(0)

if __name__ == '__main__':
    run()
