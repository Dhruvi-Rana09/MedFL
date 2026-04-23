# 🎓 MedFL Distributed Computing Presentation Guide

Welcome! This guide is tailored for your 5-person team to present the **MedFL Federated Learning Platform** as a true Distributed System.

By following this guide, you will run 5 separate pieces of the architecture on 5 separate computers, securely passing encrypted PyTorch tensors over the internet using **Tailscale**.

---

## 🛠 Phase 1: Team Pre-requisites (Do this before the presentation)

1. **Install Docker Desktop**: Every member must have Docker installed and running on their laptop.
2. **Install Tailscale**: Every member must install [Tailscale](https://tailscale.com). **One team member** (the Admin) should sign in, go to the Tailscale Admin Console -> **Users**, and click **"Invite Users"** to send an invite link to the rest of the team. The other members should sign in using that invite link so you all join the same private network (Tailnet).
3. **Get Your IPs**: Open the Tailscale app on your computer and copy your `100.x.x.x` IP address.
4. **Distribute the Code**: Ensure every team member has a copy of this entire repository.

---

## 📝 Phase 2: Configuration

1. Open `distributed_setup/medfl.env`.
2. Replace the `.x.x.x` placeholders with the actual Tailscale IPs of your team members.
3. **Crucial Step**: Send this updated `medfl.env` file to the entire team. Everyone **must** have the exact same IPs in this file.

---

## 🚀 Phase 3: The Presentation Start-Up Sequence

Because this is a distributed system with dependencies, you cannot just turn them all on at once. Follow this exact sequence during your live demo.

*Make sure you are in the `distributed_setup` directory in your terminal:*
`cd distributed_setup`

### Step 1: The State Layer (Members 1 & 5)
These services hold the database and encryption keys.
- **Member 1 (Auth)**: Run `docker compose -f compose-auth.yml up -d`
- **Member 5 (Storage)**: Run `docker compose -f compose-storage.yml up -d`

### Step 2: The Compute & Telemetry Layer (Members 3 & 4)
These services have no state, but do heavy mathematical lifting and metrics collection.
- **Member 3 (Aggregation)**: Run `docker compose -f compose-aggregation.yml up -d`
- **Member 4 (Monitoring)**: Run `docker compose -f compose-monitoring.yml up -d`

### Step 3: The Control Plane (Member 2)
The Orchestrator ties everything together. It will instantly connect to the other 4 computers.
- **Member 2 (Orchestrator)**: Run `docker compose -f compose-orchestrator.yml up -d`

### Step 4: The Edge Nodes (Hospital Data)
Because of our new Dynamic Auto-Discovery rewrite, you can add as many nodes as you want, and they will automatically appear on the Orchestrator dashboard!

- **To run Hospital A**:
  ```bash
  export HOSPITAL_ID=hospital-a
  export HOSPITAL_URL=http://<YOUR_TAILSCALE_IP>:8010
  docker compose -f compose-hospital.yml up -d
  ```
- **To run Hospital B**:
  ```bash
  export HOSPITAL_ID=hospital-b
  export HOSPITAL_URL=http://<YOUR_TAILSCALE_IP>:8010
  docker compose -f compose-hospital.yml up -d
  ```

---

## 🎤 Phase 4: Running the Demo

1. **Member 4** should open their browser to `http://localhost:8002` and project their screen. This is the **Monitoring Dashboard**.
2. Look at the "Hospital Nodes" panel. You will see "Hospital A" and "Hospital B" checking in, and **the dashboard will vividly display their remote Tailscale IP addresses (100.x.x.x)!**
3. On the Dashboard, go to **Training Controls** and click **Start Training**.
4. The dashboard will light up with activity, proving that the Central Hub just commanded the detached laptops to begin training locally, before exchanging weights over the VPN.

### 💡 Talking points for the Professor:
* *"We purposefully disaggregated our microservices across 5 physical hardware nodes to validate the resilience of the architecture."*
* *"We are utilizing a Tailscale WireGuard mesh to bypass rigid university firewalls, creating a secure overlay network for gRPC transport."*
* *"As you can see on the dashboard, the 100.x.x.x IP addresses confirm that the Hospital Nodes are physically detatched from the Aggregation server, simulating a real-world multi-institutional healthcare environment."*
