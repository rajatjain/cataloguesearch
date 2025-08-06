# Should be run from base directory

mkdir -p certs
mkdir -p credentials

# Generate self-signed certificates if they don't exist
if [ ! -f "certs/root-ca.pem" ]; then
    echo "Generating self-signed certificates..."
    
    # Generate root CA
    openssl genrsa -out certs/root-ca-key.pem 2048
    openssl req -new -x509 -sha256 -key certs/root-ca-key.pem -out certs/root-ca.pem -days 730 \
        -subj "/C=US/ST=opensearch/L=opensearch/O=opensearch/CN=root"
    
    # Generate node certificate
    openssl genrsa -out certs/node-key-temp.pem 2048
    openssl pkcs8 -inform PEM -outform PEM -in certs/node-key-temp.pem -topk8 -nocrypt -v1 PBE-SHA1-3DES -out certs/node-key.pem
    openssl req -new -key certs/node-key.pem -out certs/node.csr \
        -subj "/C=US/ST=opensearch/L=opensearch/O=opensearch/CN=opensearch"
    openssl x509 -req -in certs/node.csr -CA certs/root-ca.pem -CAkey certs/root-ca-key.pem \
        -CAcreateserial -sha256 -out certs/node.pem -days 730
    
    # Cleanup
    rm -f certs/node-key-temp.pem certs/node.csr
    
    echo "Certificates generated successfully!"
else
    echo "Certificates already exist, skipping generation."
fi
