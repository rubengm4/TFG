function setWelcomeCardTheme() {
  const hour = new Date().getHours();
  const card = document.getElementById("welcome-card");
  const textEl = document.getElementById("welcome-text");
  const userEl = document.getElementById("username");
  const projectEl = document.getElementById("project-name");
  const projectText = document.getElementById("project-text");
  const icon = document.getElementById("welcome-icon");
  const commaEl = document.getElementById("comma");

  if (
    !card ||
    !textEl ||
    !userEl ||
    !projectEl ||
    !projectText ||
    !icon ||
    !commaEl
  )
    return;

  let greeting;
  let colorUserProject;
  let gradient;

  const iconColorClasses = [
    "text-orange-600",
    "text-blue-600",
    "text-purple-300",
    "text-black",
    "text-white",
  ];

  if (hour >= 6 && hour < 12) {
    greeting = "Buenos días";
    colorUserProject = "text-orange-600";
    gradient = ["from-yellow-100", "via-amber-100", "to-orange-100"];
    textEl.classList.remove("text-white", "drop-shadow-lg");
    projectText.classList.remove("text-white", "drop-shadow-lg");
    commaEl.className = "text-black";
    iconColorClasses.forEach((c) => icon.classList.remove(c));
    icon.classList.add("text-orange-600");
  } else if (hour >= 12 && hour < 18) {
    greeting = "Buenas tardes";
    colorUserProject = "text-blue-600";
    gradient = ["from-sky-100", "via-blue-100", "to-indigo-100"];
    textEl.classList.remove("text-white", "drop-shadow-lg");
    projectText.classList.remove("text-white", "drop-shadow-lg");
    commaEl.className = "text-black";
    iconColorClasses.forEach((c) => icon.classList.remove(c));
    icon.classList.add("text-blue-600");
  } else {
    greeting = "Buenas noches";
    colorUserProject = "text-purple-300";
    gradient = ["from-indigo-900", "via-purple-900", "to-gray-900"];
    textEl.classList.add("text-white", "drop-shadow-lg");
    projectText.classList.add("text-white", "drop-shadow-lg");
    commaEl.className = "text-white drop-shadow-lg";
    iconColorClasses.forEach((c) => icon.classList.remove(c));
    icon.classList.add("text-white", "drop-shadow-lg");
  }

  textEl.textContent = greeting;
  userEl.className = `font-bold ${colorUserProject}`;
  projectEl.className = `font-bold ${colorUserProject}`;

  card.className = `w-full max-w-5xl rounded-xl shadow-lg p-6 flex flex-col items-center text-center transition-all duration-700 bg-gradient-to-br ${gradient.join(
    " ",
  )}`;
}

document.addEventListener("DOMContentLoaded", () => {
  setWelcomeCardTheme();
});

