def add_protocol(url, port):
    # Add protocol to url
    if port == 80 and 'http://' not in url:
        url = 'http://' + url
    elif port == 443 and 'https://' not in url:
        url = 'https://' + url 
    return url   

def extract_url_parts(url):
    port = 80 # Default to HTTP
    path = ''
    
    if '://' in url:
        url_parts = url.split('://', 1)
        protocol = url_parts[0]
        if (protocol == 'https'):
            port = 443
        url = url_parts[1] # Process rest of url
            
    host_and_path = url.split('/', 1)
    host = host_and_path[0]
    
    if len(host_and_path) != 1:
        path = host_and_path[1]
    
    # Check to see if port number is specified
    if ':' in host:
        host_and_port = host.split(':', 1)
        host = host_and_port[0]
        try:
            port = int(host_and_port[1])
        except ValueError:
            pass

    return host, path, port

def reformat_url(url, base_url=''):       
    # If base URL is given, prepend it to the given URL
    if base_url != '':      
        
        # Ignore relative URLs starting with '#'
        if '#' not in url:
            
            host, _, port = extract_url_parts(base_url)

            # Remove trailing slash from base url
            if base_url[-1] == '/':
                base_url = base_url[:-1]
                
            # Look for URLs starting with "./" or "//"
            if len(url) >= 2:
                # Remove "./" from the start of the URL if present
                if url[0:2] == './':
                    url = url[2:]

                # If URL starts with "//", prepend the appropriate protocol
                elif url[0:2] == '//':
                    base_url = add_protocol('', port)
                    url = url[2:]
                    if len(base_url) > 0:
                        base_url = base_url[:-1]

                # Remove "/" from the start of the URL if present
                elif url[0] == '/':
                    url = url[1:]
                    base_url = host

            if url not in base_url:
                url = base_url + '/' + url
    else:
        _, _, port = extract_url_parts(url)
        url = add_protocol(url, port)
    
    return url