# **Path Finder** 🔗🎯  

*"Because everyone is 6 handshakes away from Cleopatra"*

Ever wondered how **Lionel Messi** is connected to **Jesus**, **Shakira**, or even **Napoleon**? This project finds the wildest historical, cultural, and links between famous figures using **Neo4j** (for tangled relationships) and **FastAPI** (for speedy chaos).  

---

### **How It Works** 🔍  
- Stores people, events, and connections in a **Neo4j graph database**.  

---

## **Technologies Used** 🛠️  
- **Neo4j** (*"It’s like LinkedIn for celebrities and dead philosophers"*)  
- **FastAPI** (*"Faster than explaining your conspiracy theory"*)  

---

## **Setup & Run** 🚀  

### 1. **Clone the Project**  
```sh
git clone https://github.com/danielocho500/path_famous_finder
```

### 2. Prepare environment variables

Here is a list of enviromental variable necessary to depoy the proyect:

- PREFIX= "/prefix"
- PROD= 1 if prod, 0 if dev
- CLOUDINARY_CLOUD_NAME=
- CLOUDINARY_API_KEY=
- CLOUDINARY_API_SECRET=
- CLOUDINARY_URL=
- NEO4J_URI=
- NEO4J_USER=
- NEO4J_PASS=

### 3. Use docker compose to build and run the project
```sh
docker compose up --build
```