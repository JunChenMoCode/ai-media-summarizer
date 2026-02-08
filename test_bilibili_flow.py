import requests
import time
import json
import sys

BASE_URL = "http://127.0.0.1:18000"

def test_enqueue_and_verify(video_url):
    print(f"1. Enqueuing task for {video_url}...")
    try:
        resp = requests.post(f"{BASE_URL}/tasks/enqueue", json={"url": video_url})
        resp.raise_for_status()
        data = resp.json()
        task_id = data.get("task_id")
        print(f"   Task enqueued: {task_id}")
    except Exception as e:
        print(f"   Failed to enqueue: {e}")
        return

    print("2. Polling task status...")
    max_retries = 30  # Wait up to 30 seconds for this test (just to see it start)
    # Note: Full analysis takes longer, so we might not see 'completed' in this short script unless it's very fast.
    # But we can check if it goes to 'running'.
    
    final_md5 = None
    
    for i in range(max_retries):
        try:
            resp = requests.get(f"{BASE_URL}/tasks")
            tasks = resp.json()
            # Find our task
            my_task = next((t for t in tasks if t["id"] == task_id), None)
            
            if not my_task:
                print("   Task not found in list!")
                break
                
            status = my_task.get("status")
            progress = my_task.get("progress")
            print(f"   Status: {status}, Progress: {progress}%")
            
            if status == "completed":
                print("   Task completed!")
                result = my_task.get("result", {})
                final_md5 = result.get("md5")
                print(f"   Result MD5: {final_md5}")
                break
            elif status == "failed":
                print(f"   Task failed: {my_task.get('error')}")
                break
                
            time.sleep(2)
        except Exception as e:
            print(f"   Error polling: {e}")
            time.sleep(2)
            
    if final_md5:
        print(f"3. Verifying Analysis Data for MD5: {final_md5}")
        try:
            resp = requests.get(f"{BASE_URL}/analysis/by_md5/{final_md5}")
            if resp.status_code == 200:
                data = resp.json()
                access_url = data.get("access", {}).get("primary_url", "")
                print(f"   Primary URL: {access_url}")
                
                if access_url.startswith("/static/"):
                    print("   PASS: Primary URL is a local static path.")
                else:
                    print(f"   FAIL: Primary URL is not static: {access_url}")
                    
                artifacts = data.get("artifacts", {})
                captured_frames = artifacts.get("captured_frames", [])
                if captured_frames:
                    print(f"   Found {len(captured_frames)} captured frames.")
                    first_frame = captured_frames[0].get("json", [])[0] if captured_frames[0].get("json") else None
                    if first_frame:
                         frame_url = first_frame.get("url", "")
                         print(f"   Frame URL: {frame_url}")
                         if frame_url.startswith("/static/"):
                             print("   PASS: Frame URL is static.")
                         else:
                             print("   FAIL: Frame URL is not static.")
                else:
                    print("   WARNING: No captured frames found (might be audio or short video).")
                    
            else:
                print(f"   Failed to get analysis: {resp.status_code} {resp.text}")
        except Exception as e:
            print(f"   Error fetching analysis: {e}")
    else:
        print("   Task did not complete in time or failed. Check backend logs.")

if __name__ == "__main__":
    # Use a Bilibili video URL
    # Using a short video to speed up test if possible, or just checking if it starts.
    # 'BV1GJ411x7h7' is Rick Roll, usually reliable.
    test_url = "https://www.bilibili.com/video/BV1GJ411x7h7" 
    test_enqueue_and_verify(test_url)
