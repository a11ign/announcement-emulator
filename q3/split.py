"""Which pages the emulator may be developed against, and which it may not.

The Gate is measured on pages whose fleet transcripts were not read while the emulator was being fixed. A page is `dev` when the SHA-256 of its address,
read as a number, is even; `held` when odd. The rule is fixed before any agreement figure exists and is a function of the address only. Tools that print a
page's expected strings refuse a held page unless they are given --final, so that reading one is a decision and not an accident."""
import hashlib

def split_of(url): return 'dev' if int(hashlib.sha256(url.encode()).hexdigest(), 16) % 2 == 0 else 'held'
