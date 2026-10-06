#!/usr/bin/env python3
"""CLI utility to authenticate with My IFB Cloud via SMS OTP."""

import asyncio
import sys
from ifb_cloud import IfbCloudClient


async def main():
    print("=== My IFB Cloud OTP Authenticator ===")
    phone = input("Enter your registered mobile number (e.g., 98XXXXXXXX): ").strip()
    if not phone:
        print("Error: Mobile number is required.")
        sys.exit(1)

    calling_code = input("Country calling code [default +91]: ").strip() or "+91"

    client = IfbCloudClient()
    try:
        print(f"\nRequesting OTP for {calling_code} {phone}...")
        resp = await client.request_otp(phone=phone, calling_code=calling_code)
        print(f"OTP Request Response: {resp.get('message', 'OTP sent successfully')}")

        otp = input("\nEnter the 6-digit OTP received via SMS: ").strip()
        print("Verifying OTP...")
        verify_resp = await client.verify_otp(phone=phone, otp=otp, calling_code=calling_code)
        print("\n--- Authentication Successful! ---")
        token_str = client.token or ""
        masked_token = f"{token_str[:8]}...{token_str[-4:]}" if len(token_str) > 12 else "***"
        print(f"Bearer Token: {masked_token} (Masked for privacy - do not share full tokens publicly)")
        print(f"User ID:      {client.user_id}")

        print("\nFetching registered appliances...")
        devices = await client.get_all_devices()
        print(f"Discovered {len(devices)} device(s):")
        for dev in devices:
            print(f"  - {dev.name} (MAC: {dev.mac}, Model: {dev.model_name}, Online: {dev.is_online})")

    except Exception as err:
        print(f"\nError: {err}")
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
