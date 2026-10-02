package com.example.demo.service;

import com.example.demo.client.ChatClient;
import com.example.demo.dto.ChatRequestDto;
import com.example.demo.dto.ChatResponseDto;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class ChatService {

    private final ChatClient chatClient;
    private final Map<String, String> userConversationMap = new ConcurrentHashMap<>();

    public ChatService(ChatClient chatClient) {
        this.chatClient = chatClient;
    }

    /**
     * 发送消息（自动管理会话）
     */
    public String chat(String userId, String message) {
        return chat(userId, message, null);
    }

    /**
     * 发送消息（带上下文长度控制）
     */
    public String chat(String userId, String message, Integer maxHistory) {
        String conversationId = userConversationMap.get(userId);
        ChatRequestDto request = maxHistory != null
                ? new ChatRequestDto(conversationId, message, maxHistory)
                : new ChatRequestDto(conversationId, message);

        ChatResponseDto response = chatClient.chat(request);
        userConversationMap.put(userId, response.conversationId());

        return response.reply();
    }

    /**
     * 开启新对话
     */
    public String startNewChat(String userId, String message) {
        ChatResponseDto response = chatClient.startConversation(message);
        userConversationMap.put(userId, response.conversationId());
        return response.reply();
    }

    /**
     * 清空用户会话
     */
    public void clearUserChat(String userId) {
        String conversationId = userConversationMap.remove(userId);
        if (conversationId != null) {
            chatClient.clearConversationSync(conversationId);
        }
    }

    /**
     * 获取会话ID
     */
    public String getConversationId(String userId) {
        return userConversationMap.get(userId);
    }

    /**
     * 是否有活跃会话
     */
    public boolean hasActiveConversation(String userId) {
        return userConversationMap.containsKey(userId);
    }
}