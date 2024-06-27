import { useEffect, useRef } from "react";
import ChatBubble from "./chatBubble";
import Feedback from "./Feedback";
import TypingIndicator from "./TypingIndicator";

import styles from "./index.module.css";

export default function Messages({
  height,
  chatHistory,
  choice,
  setChoice,
  setSelectedButton,
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (containerRef.current && containerRef.current.lastElementChild) {
      containerRef.current.lastElementChild.scrollIntoView({
        behavior: "smooth",
        block: "end",
      });
    }
  }, [choice, chatHistory]);

  // fit chat bubble width to text width
  useEffect(() => {
    const messageDivs = document.querySelectorAll('[data-role="message"]');
    messageDivs?.forEach((m, index) => {
      const range = document.createRange();
      const text = m?.childNodes[0];
      if (text) {
        range.setStartBefore(text);
        range.setEndAfter(text);
        const clientRect = range.getBoundingClientRect();
        m.style.width = `${clientRect.width}px`;
      }
    });
  }, []);

  const handleButtonClick = (index, message) => {
    setSelectedButton(index);
    setChoice(message);
  };

  const messageHistory = (message, index, length) => {
    switch (message.type) {
      case "text":
        return (
          <ChatBubble
            key={index}
            message={message}
            length={length}
            index={index}
          />
        );
      case "feedback":
        return (
          <Feedback
            key={index}
            handleButtonClick={handleButtonClick}
            title={message.content.title}
            body={message.content.body}
            choice={message.content.choice}
          />
        );
      case "typingIndicator":
        return <TypingIndicator key={index} />;
      default:
        return "";
    }
  };

  return (
    <div
      style={{ height: height }}
      className={styles.wrapper}
      ref={containerRef}
    >
      <div className={styles.messageWrapper}>
        {chatHistory?.map((message, index) => {
          return messageHistory(message, index, chatHistory.length);
        })}
      </div>
    </div>
  );
}