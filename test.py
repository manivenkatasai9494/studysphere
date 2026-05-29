from supabase import create_client

url = "https://bukwlsrpcyqjexqjmwis.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ1a3dsc3JwY3lxamV4cWptd2lzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAwNDk4MzMsImV4cCI6MjA5NTYyNTgzM30.dpxkTwZ-xCfe4UUAeccExrM4IJId_xy8-meSZ-SWbek"  # hide most of it

supabase = create_client(url, key)

res = supabase.auth.sign_up({
    "email": "mani123@gmail.com",
    "password": "Password123!"
})

print(res)