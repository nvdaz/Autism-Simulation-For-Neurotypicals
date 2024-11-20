import { cn } from "@/lib/utils";
import { formatRelative } from "date-fns";
import { motion } from "framer-motion";
import { Fragment, useMemo } from "react";
import { useAuth } from "../auth-provider";
import { Button } from "./button";
import { ScrollArea } from "./scroll-area";
import { Separator } from "./separator";

export interface Message {
  index?: number;
  id?: number;
  content: string;
  sender: string;
  avatarUrl?: string;
  isOutgoing?: boolean;
  created_at: string;
}

export interface InChatFeedback {
  index?: number;
  feedback: {
    title: string;
    body: string;
  };
  alternative: string;
  alternative_feedback: string;
  rating: number | null;
  created_at: string;
}

const isFeedback = (msg: Message | InChatFeedback): msg is InChatFeedback => {
  return "feedback" in msg;
};

function capitalize(str: string) {
  return str.charAt(0).toUpperCase() + str.slice(1);
}

export function ChatInterface({
  messages,
  typing,
  chatEnd,
  handleRate,
}: {
  messages: (Message | InChatFeedback)[];
  typing: boolean;
  chatEnd: React.RefObject<HTMLDivElement>;
  handleRate: (index: number, rating: number) => void;
}) {
  const { user } = useAuth();

  const groupedMessages = useMemo(() => {
    const grouped = messages.reduce((acc, msg, i) => {
      msg.index = i;
      if (acc.length === 0) {
        return [[msg]];
      }

      const lastGroup = acc[acc.length - 1];
      const lastMsg = lastGroup[lastGroup.length - 1];
      if (
        Date.parse(msg.created_at) - Date.parse(lastMsg.created_at) <
        1000 * 60 * 5
      ) {
        lastGroup.push(msg);
      } else {
        acc.push([msg]);
      }

      return acc;
    }, [] as (Message | InChatFeedback)[][]);

    return grouped;
  }, [messages]);

  return (
    <ScrollArea className="h-full w-full">
      <div className="space-y-4 p-4 flex flex-col">
        {groupedMessages.map((group, index) => (
          <Fragment key={index}>
            <div className="text-center text-xs text-gray-500 dark:text-gray-400 mb-4 mt-2">
              {capitalize(formatRelative(group[0].created_at, new Date()))}
            </div>
            {group.map((msg, index) =>
              isFeedback(msg) ? (
                <FeedbackBubble
                  key={index}
                  feedback={msg}
                  handleRate={handleRate}
                  index={msg.index!}
                />
              ) : (
                <ChatBubble
                  key={index}
                  content={msg.content}
                  sender={msg.sender}
                  avatarUrl={msg.avatarUrl}
                  isOutgoing={msg.sender === user!.name}
                />
              )
            )}
          </Fragment>
        ))}
        {typing && (
          <div className="justify-end p-3">
            <TypingIndicator />
          </div>
        )}
      </div>
      <div ref={chatEnd} />
    </ScrollArea>
  );
}

interface ChatBubbleProps {
  content: string;
  sender: string;
  avatarUrl?: string;
  isOutgoing?: boolean;
}

function ChatBubble({ content: message, isOutgoing = false }: ChatBubbleProps) {
  return (
    <div
      className={`flex ${isOutgoing ? "justify-end" : "justify-start"} my-4`}
    >
      <div
        className={`flex ${
          isOutgoing ? "flex-row-reverse" : "flex-row"
        } items-end`}
      >
        <div
          className={`mx-2 ${
            isOutgoing ? "items-end" : "items-start"
          } flex flex-col`}
        >
          <div
            className={`${isOutgoing ? "bg-blue-500" : "bg-secondary"} ${
              isOutgoing ? "text-white" : "text-secondary-foreground"
            } rounded-xl p-3 max-w-xs md:max-w-sm lg:max-w-md w-fit ${
              isOutgoing ? "rounded-br-none" : "rounded-bl-none"
            }`}
          >
            <p className="text-sm">{message}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

const FEEDBACK_RESPONSES = ["No", "Neutral", "Yes"];

function FeedbackBubble({
  feedback,
  handleRate,
  index,
}: {
  feedback: InChatFeedback;
  handleRate: (index: number, rating: number) => void;
  index: number;
}) {
  return (
    <div className="w-full flex items-center justify-center">
      <div className="max-w-screen-md my-4">
        <div className="flex items-end">
          <div className="mx-2 flex flex-col">
            <div className="bg-accent text-accent-foreground rounded-md p-3">
              <h2 className="font-semibold">{feedback.feedback.title}</h2>
              <p className="text-sm">{feedback.feedback.body}</p>
              <h2 className="mt-4 font-semibold">Instead, You Could Say:</h2>
              <p className="text-sm rounded-md bg-gray-300 p-2 my-1">
                {feedback.alternative}
              </p>
              <p className="text-sm">{feedback.alternative_feedback}</p>
              <Separator className="mt-4" />
              <h3 className="mt-2 font-medium">
                Does this feedback make sense to you?
              </h3>
              <div className="flex justify-center space-x-4 mt-2">
                {[3, 2, 1].map((i) => (
                  <Button
                    key={i}
                    onClick={() => handleRate(index, i)}
                    className={cn(
                      "h-8 p-2 w-[80px]",
                      feedback.rating === i
                        ? "bg-black text-white cursor-default hover:bg-black"
                        : "bg-gray-100 text-black hover:bg-gray-100"
                    )}
                    variant={feedback.rating === i ? "default" : "outline"}
                  >
                    {FEEDBACK_RESPONSES[i - 1]}
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function TypingIndicator({
  background = true,
}: {
  background?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-center space-x-2 p-3 rounded-xl max-w-fit",
        background && "bg-secondary"
      )}
    >
      <motion.span
        className="w-2 h-2 bg-gray-400 rounded-full"
        animate={{ backgroundColor: ["#D1D5DB", "#9CA3AF", "#D1D5DB"] }}
        transition={{ repeat: Infinity, duration: 1 }}
      />
      <motion.span
        className="w-2 h-2 bg-gray-400 rounded-full"
        animate={{ backgroundColor: ["#D1D5DB", "#9CA3AF", "#D1D5DB"] }}
        transition={{
          repeat: Infinity,
          duration: 1,
          delay: 0.2,
        }}
      />
      <motion.span
        className="w-2 h-2 bg-gray-400 rounded-full"
        animate={{ backgroundColor: ["#D1D5DB", "#9CA3AF", "#D1D5DB"] }}
        transition={{
          repeat: Infinity,
          duration: 1,
          delay: 0.4,
        }}
      />
    </div>
  );
}
